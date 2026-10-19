"""
TTS 统一网关

所有 TTS 引擎通过同一个地址访问，Java 配置一次永不改动。

启动:  uvicorn app:app --host 0.0.0.0 --port 9000
调用:  POST http://127.0.0.1:9000/tts/edge
       POST http://127.0.0.1:9000/tts/supernatural
       POST http://127.0.0.1:9000/tts/sherpa
"""

import io
import os
import sys
import uuid
from typing import Any, Dict

import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tts_common import (
    ErrorResponse,
    create_tts_request_model,
    create_verify_api_key,
    error_body,
    register_error_handlers,
    require_startup_auth,
)

# ============================================================================
# 配置
# ============================================================================

require_startup_auth()

API_KEY = os.getenv("TTS_API_KEY", "my-fixed-key-2026").strip()
REQUEST_TIMEOUT = float(os.getenv("TTS_REQUEST_TIMEOUT", "120"))

# 四个后端服务（各自独立端口）
_BACKENDS = {
    "http://127.0.0.1:8000": ["edge"],                                                    # ① TeleAI
    "http://127.0.0.1:8001": ["edge"],                                                    # ② Edge TTS
    "http://127.0.0.1:8002": ["sherpa"],                                                  # ③ Sherpa
    "http://127.0.0.1:8900": ["supernatural", "realtime", "offline"],                     # ④ Tianyi
}
ENGINE_BACKENDS: Dict[str, str] = {
    engine: url for url, engines in _BACKENDS.items() for engine in engines
}

# 全部引擎支持的格式
ALL_FORMATS = {"WAV", "MP3", "FLAC"}
ALL_ENGINES = frozenset(ENGINE_BACKENDS.keys())

TTSRequest = create_tts_request_model(
    engine_default="edge",
    voice_default="zh-CN-XiaoxiaoNeural",
    format_default="WAV",
    supported_engines=ALL_ENGINES,
    supported_formats=frozenset(ALL_FORMATS),
    max_text_length=None,
)

app = FastAPI(
    title="TTS Unified Gateway",
    description="统一 TTS 网关 — 一个地址调用所有引擎",
    version="1.0.0",
)
register_error_handlers(app)
verify_api_key = create_verify_api_key(API_KEY)


# ============================================================================
# 路由
# ============================================================================

@app.get("/health", summary="Health check", response_model=Dict[str, str])
def health(_auth: None = Depends(verify_api_key)) -> Dict[str, str]:
    return {"status": "ok", "gateway": "true"}


@app.head("/tts", summary="TTS response preflight")
def tts_head(_auth: None = Depends(verify_api_key)) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="preview.mp3"'},
    )


def _proxy(engine: str, payload: TTSRequest) -> StreamingResponse:
    backend = ENGINE_BACKENDS.get(engine)
    if not backend:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_body(42200, f"Unknown engine: {engine}"),
        )

    payload.engine = engine  # 用 URL 中的引擎覆盖 body 中的默认值
    # Edge TTS 只支持 MP3，其他引擎默认 WAV
    if engine == "edge" and payload.format.upper() not in ("MP3",):
        payload.format = "MP3"
    target_url = f"{backend}/tts/{engine}"
    req_id = payload.req_id or uuid.uuid4().hex

    try:
        resp = requests.post(
            target_url,
            json=payload.dict(exclude_none=True),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": API_KEY,
            },
            timeout=REQUEST_TIMEOUT,
            stream=True,
        )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50201, "Backend TTS request failed.", str(e)),
        ) from e

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:500],
        )

    return StreamingResponse(
        resp.iter_content(chunk_size=8192),
        media_type=resp.headers.get("Content-Type", "audio/mpeg"),
        headers={
            "Content-Disposition": resp.headers.get("Content-Disposition", f'inline; filename="{req_id}"'),
            "X-Request-ID": req_id,
            "X-TTS-Engine": engine,
            "X-Backend": backend,
        },
    )


# POST /tts — 引擎在 body 里
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
    return _proxy(payload.engine, payload)


# POST /tts/{engine} — 引擎直连
for _engine in sorted(ENGINE_BACKENDS.keys()):
    def _make_route(engine_name: str):
        @app.post(
            f"/tts/{engine_name}",
            summary=f"TTS synthesis via {engine_name}",
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
            return _proxy(_eng, payload)
        return _engine_tts
    _make_route(_engine)


@app.post("/text/", include_in_schema=False)
def legacy_tts(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return _proxy(payload.engine, payload)


@app.head("/text/", include_in_schema=False)
def legacy_head() -> StreamingResponse:
    return tts_head()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
