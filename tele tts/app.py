"""
================================================================================
TeleAI TTS 统一 HTTP 接口 (app.py)
================================================================================
整个项目只有一个文件，包含：配置 → 数据模型 → 上游签名 → 双引擎合成 → 认证 → API 路由

启动：uvicorn app:app --host 0.0.0.0 --port 8000
文档：http://127.0.0.1:8000/docs
================================================================================
"""

# ============================================================================
# 一、导入依赖
# ============================================================================
import asyncio          # 运行 edge-tts 的异步流
import base64           # 解码上游返回的 Base64 音频
import hashlib          # HMAC-SHA256 签名
import hmac
import io               # 内存文件对象，不写磁盘
import logging
import os               # 读取环境变量
import sys              # sys.path for tts_common import
import time             # 生成时间戳
import urllib.parse     # URL 编码
import uuid             # 生成请求追踪 ID
from typing import Any, Dict, Tuple

import edge_tts                              # 微软 Edge 免费 TTS
import requests                              # 调用上游 TeleAI HTTP API
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse  # StreamingResponse = 内存流返回，不写磁盘

from SignUtils import (                      # 你的 AppID / Secret Key 密钥常量
    EXPIRATION_IN_SECONDS,                   # 签名有效期（12 小时）
    PUBLIC_NETWORK_SING_HEADER,              # 公网鉴权头部标识
    REGION,                                  # 区域
    SIGNED_HEADERS,                          # 参与签名的请求头
    X_APP_ID,                                # 应用 ID
    X_APP_KEY,                               # 应用密钥
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tts_common import (  # noqa: E402
    EngineInfo,
    ErrorResponse,
    create_tts_request_model,
    create_verify_api_key,
    error_body,
    pitch_to_ssml,
    speed_to_rate,
    volume_to_ssml,
    media_type_for,
    register_error_handlers,
    require_startup_auth,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 二、全局配置（可通过环境变量覆盖）
# ============================================================================

# -- 启动认证（TTS_STARTUP_USER / TTS_STARTUP_PASS 设置后生效） --
require_startup_auth()

# -- 调用方认证（TTS_API_KEY 为空时不需要认证） --
API_KEY = os.getenv("TTS_API_KEY", "my-fixed-key-2026").strip()

# -- 上游请求超时和 HTTPS 证书校验 --
REQUEST_TIMEOUT_SECONDS = float(os.getenv("TTS_REQUEST_TIMEOUT", "120"))  # 默认 120 秒
VERIFY_TLS = os.getenv("TTS_VERIFY_TLS", "false").strip().lower() in {
    "1", "true", "yes", "on",
}  # 默认关闭证书校验（内网环境）

# -- TTS 引擎列表（引擎名 → 上游 URL） --
# edge 引擎走本地 edge-tts 库，不走网络，所以 URL 为空
TTS_ENGINES: Dict[str, str] = {
    "supernatural": "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural",
    "realtime":     "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural",
    "offline":      "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/offLineSynthesis",
    "edge":         "",  # 本地 edge-tts，不走上游 API
}

SUPPORTED_FORMATS = {"WAV", "MP3", "FLAC"}

TTSRequest = create_tts_request_model(
    engine_default="supernatural",
    voice_default="zh-CN-YunxiNeural",
    format_default="WAV",
    supported_engines=frozenset(TTS_ENGINES.keys()),
    supported_formats=frozenset(SUPPORTED_FORMATS),
    max_text_length=None,  # No text length limit for upstream API
)

# -- FastAPI 应用实例 --
app = FastAPI(
    title="TeleAI Unified TTS API",
    version="1.0.0",
    description="Unified FastAPI HTTP interface for TeleAI TTS engines.",
)
register_error_handlers(app)
verify_api_key = create_verify_api_key(API_KEY)


# ============================================================================
# 三、上游 TeleAI 认证签名（HMAC-SHA256）
# ============================================================================
# 每次调 TeleAI API 时自动生成签名，不需要手动处理。
# 签名公式：
#   signing_key = HMAC-SHA256(AppKey, header/appid/region/timestamp/expiration)
#   signature   = HMAC-SHA256(signing_key, "POST\n/canonical/uri\n\ncanonical_headers")
#   Authorization = header/appid/region/timestamp/expiration/signed_headers/signature

def normalize(value: str, encoding_slash: bool = True) -> str:
    """URL 编码，保留安全和分隔字符。"""
    safe_chars = "~()*!'/" if encoding_slash else "~()*!'"
    return urllib.parse.quote(value, safe=safe_chars)


def generate_canonical_uri(url: str) -> str:
    """从完整 URL 中提取并编码路径部分。"""
    parsed_url = urllib.parse.urlparse(url)
    return "/".join(normalize(segment, False) for segment in parsed_url.path.split("/"))


def generate_authorization(
    url: str, method: str = "POST", canonical_query_string: str = ""
) -> str:
    """
    生成 TeleAI 上游接口的 Authorization 签名字符串。

    步骤：
    1. 用 AppKey 对签名密钥串做 HMAC-SHA256 → signing_key
    2. 用 signing_key 对规范请求串做 HMAC-SHA256 → signature
    3. 拼接最终的 Authorization 头值
    """
    timestamp = str(int(time.time()))
    canonical_uri = generate_canonical_uri(url)
    canonical_headers = f"x-app-id:{urllib.parse.quote(X_APP_ID.strip(), safe='')}"
    signed_headers = ";".join(sorted(set(SIGNED_HEADERS.split(";"))))

    # 步骤 1：生成签名密钥
    signing_key_str = (
        f"{PUBLIC_NETWORK_SING_HEADER}/{X_APP_ID}/{REGION}/"
        f"{timestamp}/{EXPIRATION_IN_SECONDS}"
    )
    signing_key = hmac.new(
        X_APP_KEY.encode("utf-8"),
        signing_key_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # 步骤 2：生成签名
    canonical_request = (
        f"{method.upper()}\n{canonical_uri}\n"
        f"{canonical_query_string}\n{canonical_headers}"
    )
    signature = hmac.new(
        signing_key.encode("utf-8"),
        canonical_request.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # 步骤 3：拼接
    return f"{signing_key_str}/{signed_headers}/{signature}"


def build_headers(tts_url: str) -> Dict[str, str]:
    """构建发送给上游 TeleAI 的 HTTP 请求头（含签名）。"""
    return {
        "Content-Type": "application/json",
        "X-APP-ID": X_APP_ID,
        "Authorization": generate_authorization(tts_url),
    }


def build_upstream_payload(payload: TTSRequest, req_id: str) -> Dict[str, Any]:
    """把客户端请求体转成上游 TeleAI 需要的格式。"""
    request_data: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "req_id": req_id,
        "text": payload.text,
        "format": "MP3",               # 强制 MP3，统一输出格式
        "voice": payload.voice,
    }
    # 合并客户端透传的额外参数
    request_data.update(payload.extra_params)
    return request_data


# ============================================================================
# 四、TTS 引擎 — 远端 TeleAI 合成
# ============================================================================

def request_tts(payload: TTSRequest) -> Tuple[bytes, str, str]:
    """
    调上游 TeleAI API 合成语音。

    流程：
    1. 生成签名 → 2. POST 请求 → 3. 提取 result.audio(Base64)
    → 4. Base64 解码 → 5. 返回音频字节

    返回：(音频字节, 音频格式, 请求ID)
    """
    tts_url = TTS_ENGINES[payload.engine]
    req_id = payload.req_id or uuid.uuid4().hex
    request_data = build_upstream_payload(payload, req_id)

    # --- 发起 HTTP 请求 ---
    try:
        response = requests.post(
            tts_url,
            json=request_data,
            headers=build_headers(tts_url),
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=VERIFY_TLS,
        )
    except requests.RequestException as exc:
        logger.exception("TTS upstream request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50201, "TTS upstream request failed.", str(exc)),
        ) from exc

    # --- 检查上游 HTTP 状态 ---
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(
                50202,
                "TTS upstream returned non-200 status.",
                {"status_code": response.status_code, "body": response.text[:1000]},
            ),
        )

    # --- 提取并解码 Base64 音频 ---
    try:
        response_data = response.json()
        audio_base64 = response_data["result"]["audio"]  # 上游返回的音频是 Base64 字符串
        audio_bytes = base64.b64decode(audio_base64)      # 解码为二进制
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(
                50203,
                "TTS upstream response does not contain valid result.audio.",
                {"body": response.text[:1000]},
            ),
        ) from exc

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50204, "TTS upstream returned empty audio."),
        )

    return audio_bytes, "mp3", req_id


# ============================================================================
# 五、TTS 引擎 — 本地 Edge TTS 合成
# ============================================================================

def request_edge_tts(payload: "TTSRequest") -> Tuple[bytes, str, str]:
    """
    使用 edge-tts 库本地合成语音（免费，不走网络）。

    流程：
    1. 参数转换（speed→rate, pitch→"+xxHz", volume→"+xx%"）
    2. 有情感风格时用 SSML 标记语言，无风格时传纯文本
    3. 调 edge_tts.Communicate 流式合成
    4. 收集所有音频块 → 返回完整字节

    返回：(音频字节, "mp3", 请求ID)
    """
    req_id = payload.req_id or uuid.uuid4().hex
    voice = payload.voice
    rate = speed_to_rate(payload.speed)
    pitch = pitch_to_ssml(payload.pitch)
    volume = volume_to_ssml(payload.volume)

    # --- 构建合成文本：有风格用 SSML，无风格用纯文本 ---
    use_style = payload.style.strip().lower() != "general"
    if use_style:
        # SSML = Speech Synthesis Markup Language，可以控制情感、语速、音调
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"'
            f' xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="zh-CN">'
            f'<voice name="{voice}">'
            f'<mstts:express-as style="{payload.style}">'
            f'<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">'
            f"{payload.text}"
            f"</prosody>"
            f"</mstts:express-as>"
            f"</voice>"
            f"</speak>"
        )
        text = ssml
    else:
        text = payload.text

    # --- edge-tts 是异步库，用 asyncio.run() 驱动 ---
    async def _stream():
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":        # 只收集音频帧，跳过 WordBoundary 等
                audio_bytes += chunk["data"]
        return audio_bytes

    try:
        audio_bytes = asyncio.run(_stream())
    except Exception as exc:
        logger.exception("Edge TTS synthesis failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50210, "Edge TTS synthesis failed.", str(exc)),
        ) from exc

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50211, "Edge TTS returned empty audio."),
        )

    # edge-tts 只出 MP3，返回 "mp3" 确保 Content-Type 正确
    return audio_bytes, "mp3", req_id


# ============================================================================
# 六、API 路由
# ============================================================================

# ------ GET /health ------ 健康检查 ------
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


# ------ POST /tts ------ 统一合成（引擎在请求体中指定，向后兼容）------
@app.post(
    "/tts",
    summary="Unified TTS synthesis (engine in body)",
    responses={
        200: {"description": "Binary audio stream."},
        401: {"model": ErrorResponse, "description": "API key authentication failed."},
        422: {"model": ErrorResponse, "description": "请求参数不合法"},
        502: {"model": ErrorResponse, "description": "上游 TTS 服务异常"},
    },
)
def tts(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return _synthesize(payload)


# ------ POST /tts/{engine} ------ 引擎直连路由 ------
# 支持的引擎：edge, supernatural, realtime, offline
for _engine in sorted(TTS_ENGINES.keys()):
    def _make_endpoint(engine_name: str):
        @app.post(
            f"/tts/{engine_name}",
            summary=f"TTS synthesis via {engine_name} engine",
            responses={
                200: {"description": "Binary audio stream."},
                401: {"model": ErrorResponse, "description": "API key authentication failed."},
                422: {"model": ErrorResponse, "description": "请求参数不合法"},
                502: {"model": ErrorResponse, "description": "上游 TTS 服务异常"},
            },
        )
        def _engine_tts(
            payload: TTSRequest,
            _auth: None = Depends(verify_api_key),
            _engine_name: str = engine_name,
        ) -> StreamingResponse:
            payload.engine = _engine_name
            return _synthesize(payload)
        return _engine_tts
    _make_endpoint(_engine)


def _synthesize(payload: TTSRequest) -> StreamingResponse:
    if payload.engine == "edge":
        audio_bytes, audio_format, req_id = request_edge_tts(payload)
    else:
        audio_bytes, audio_format, req_id = request_tts(payload)

    media_type, extension = media_type_for(audio_format)
    audio_file = io.BytesIO(audio_bytes)
    headers = {
        "Content-Disposition": f'inline; filename="{req_id}.{extension}"',
        "X-Request-ID": req_id,
        "X-TTS-Engine": payload.engine,
        "Content-Length": str(len(audio_bytes)),
    }
    return StreamingResponse(audio_file, media_type=media_type, headers=headers)


# ------ POST /text/ ------ 旧版兼容端点（不在 OpenAPI 文档中显示） ------
@app.post("/text/", include_in_schema=False)
def legacy_text_to_speech(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return _synthesize(payload)


@app.head("/text/", include_in_schema=False)
def legacy_text_to_speech_head() -> StreamingResponse:
    return tts_head()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
