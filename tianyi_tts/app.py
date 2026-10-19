"""
Tianyi TTS 服务 — TeleAI 超自然/实时/离线语音合成

遵循 TTS 统一 API 标准。
上游 API: openapi.teleagi.cn

环境变量:
  TIANYI_APP_ID   — TeleAI 应用 ID
  TIANYI_APP_KEY  — TeleAI 应用密钥
  TTS_API_KEY     — 本服务固定 API Key（默认 my-fixed-key-2026）
"""

import hashlib
import hmac
import io
import json
import logging
import os
import sys
import time
import urllib.parse
import uuid
from typing import Any, Dict, Tuple

import requests
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse

# ---- 共享模块 ----
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tts_common import (  # noqa: E402
    ErrorResponse,
    create_tts_request_model,
    create_verify_api_key,
    error_body,
    media_type_for,
    register_error_handlers,
    require_startup_auth,
)

logger = logging.getLogger(__name__)

# ============================================================================
# 配置
# ============================================================================

require_startup_auth()

API_KEY = os.getenv("TTS_API_KEY", "my-fixed-key-2026").strip()
APP_ID = os.getenv("TIANYI_APP_ID", "97316fce99ea440dadf4c10864220ae9").strip()
APP_KEY = os.getenv("TIANYI_APP_KEY", "285d8ca376fa46fb8972e5ac9cc0801b").strip()

REQUEST_TIMEOUT = float(os.getenv("TTS_REQUEST_TIMEOUT", "120"))
VERIFY_TLS = os.getenv("TTS_VERIFY_TLS", "false").strip().lower() in {"1", "true", "yes", "on"}

AUTH_HEADER = "teleai-cloud-auth-v1"
REGION = "QG"
EXPIRATION = "43200"

# 引擎 → 上游 URL
ENGINES: Dict[str, str] = {
    "supernatural": "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural",
    "realtime":     "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural",
    "offline":      "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/offLineSynthesis",
}

FORMATS = {"WAV"}

# ---- 请求模型 ----
TTSRequest = create_tts_request_model(
    engine_default="supernatural",
    voice_default="xianliaonv",
    format_default="WAV",
    supported_engines=frozenset(ENGINES.keys()),
    supported_formats=frozenset(FORMATS),
    max_text_length=None,
)

# ---- FastAPI ----
app = FastAPI(
    title="Tianyi TTS",
    description="TeleAI 超自然/实时/离线语音合成 — 统一 TTS API 标准",
    version="1.0.0",
)
register_error_handlers(app)
verify_api_key = create_verify_api_key(API_KEY)


# ============================================================================
# 上游签名
# ============================================================================

def _generate_authorization(url: str) -> str:
    timestamp = str(int(time.time()))

    # 规范化 URI
    parsed = urllib.parse.urlparse(url)
    path = "/".join(
        urllib.parse.quote(s, safe="~()*!'") for s in parsed.path.split("/") if s
    )

    canonical_headers = f"x-app-id:{urllib.parse.quote(APP_ID, safe='')}"
    signed_headers = "x-app-id"

    # 签名密钥
    signing_key_str = f"{AUTH_HEADER}/{APP_ID}/{REGION}/{timestamp}/{EXPIRATION}"
    signing_key = hmac.new(
        APP_KEY.encode("utf-8"), signing_key_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # 签名
    canonical_request = f"POST\n/{path}\n\n{canonical_headers}"
    signature = hmac.new(
        signing_key.encode("utf-8"), canonical_request.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return f"{signing_key_str}/{signed_headers}/{signature}"


def _build_headers(url: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-APP-ID": APP_ID,
        "Authorization": _generate_authorization(url),
    }


# ============================================================================
# 合成核心
# ============================================================================

def _synthesize(payload: TTSRequest) -> StreamingResponse:

    upstream_url = ENGINES.get(payload.engine, "")
    if not upstream_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50201, "No upstream URL configured for this engine."),
        )

    req_id = payload.req_id or uuid.uuid4().hex

    request_data: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "req_id": req_id,
        "text": payload.text,
        "voice": payload.voice,
        "format": payload.format.upper(),
    }
    request_data.update(payload.extra_params)

    try:
        resp = requests.post(
            upstream_url,
            json=request_data,
            headers=_build_headers(upstream_url),
            timeout=REQUEST_TIMEOUT,
            verify=VERIFY_TLS,
        )
    except requests.RequestException as exc:
        logger.exception("Upstream request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50201, "Upstream TTS request failed.", str(exc)),
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50202, f"Upstream returned {resp.status_code}.", resp.text[:500]),
        )

    try:
        result = resp.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50203, "Upstream response is not valid JSON."),
        ) from None

    if result.get("status") != 10000:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(
                50202,
                f"Upstream error: {result.get('status_msg', 'unknown')}",
                result,
            ),
        )

    audio_data = result.get("result", {}).get("audio", "")
    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50204, "Upstream returned empty audio."),
        )

    import base64
    try:
        audio_bytes = base64.b64decode(audio_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50203, "Failed to decode audio data.", str(exc)),
        ) from exc

    audio_fmt = payload.format.upper()
    media_type, extension = media_type_for(audio_fmt)
    audio_file = io.BytesIO(audio_bytes)
    headers = {
        "Content-Disposition": f'inline; filename="{req_id}.{extension}"',
        "Content-Length": str(len(audio_bytes)),
        "X-Request-ID": req_id,
        "X-TTS-Engine": payload.engine,
    }
    return StreamingResponse(audio_file, media_type=media_type, headers=headers)


# ============================================================================
# 路由
# ============================================================================

@app.get("/health", summary="Health check", response_model=Dict[str, str])
def health(_auth: None = Depends(verify_api_key)) -> Dict[str, str]:
    return {"status": "ok"}


@app.head("/tts", summary="TTS response preflight")
def tts_head(_auth: None = Depends(verify_api_key)) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="preview.mp3"'},
    )


@app.post(
    "/tts",
    summary="Unified TTS synthesis (engine in body)",
    responses={
        200: {"description": "Binary audio stream."},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
def tts(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return _synthesize(payload)


# 引擎直连路由
for _engine in sorted(ENGINES.keys()):
    def _make_route(engine_name: str):
        @app.post(
            f"/tts/{engine_name}",
            summary=f"TTS synthesis via {engine_name} engine",
            responses={
                200: {"description": "Binary audio stream."},
                401: {"model": ErrorResponse},
                422: {"model": ErrorResponse},
                502: {"model": ErrorResponse},
            },
        )
        def _engine_tts(
            payload: TTSRequest,
            _auth: None = Depends(verify_api_key),
            _eng: str = engine_name,
        ) -> StreamingResponse:
            payload.engine = _eng
            return _synthesize(payload)
        return _engine_tts
    _make_route(_engine)


@app.post("/text/", include_in_schema=False)
def legacy_tts(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return _synthesize(payload)


@app.head("/text/", include_in_schema=False)
def legacy_head() -> StreamingResponse:
    return tts_head()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8900)
