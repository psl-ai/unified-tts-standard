import io
import os
import sys
import uuid
from typing import Any, Dict

import edge_tts
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse

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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
require_startup_auth()

PORT = int(os.getenv("PORT", "8001"))
API_KEY = os.getenv("TTS_API_KEY", "my-fixed-key-2026").strip()
ENGINE_NAME = "edge"
MAX_TEXT_LENGTH = int(os.getenv("TTS_MAX_TEXT_LENGTH", "1000"))

TTSRequest = create_tts_request_model(
    engine_default="edge",
    voice_default="zh-CN-YunxiNeural",
    format_default="MP3",
    supported_engines=frozenset({"edge"}),
    supported_formats=frozenset({"MP3"}),
    max_text_length=MAX_TEXT_LENGTH,
)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Edge Unified TTS API",
    version="1.0.0",
    description="Unified FastAPI HTTP interface for edge-tts.",
)
register_error_handlers(app)
verify_api_key = create_verify_api_key(API_KEY)


# ---------------------------------------------------------------------------
# TTS synthesis
# ---------------------------------------------------------------------------
async def generate_audio(payload: TTSRequest) -> bytes:
    communicate = edge_tts.Communicate(
        text=payload.text,
        voice=payload.voice,
        rate=speed_to_rate(payload.speed),
        pitch=pitch_to_ssml(payload.pitch),
        volume=volume_to_ssml(payload.volume),
    )
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
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


async def _synthesize(payload: TTSRequest) -> StreamingResponse:
    req_id = payload.req_id or uuid.uuid4().hex
    try:
        audio_bytes = await generate_audio(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50210, "Edge TTS synthesis failed.", str(exc)),
        ) from exc

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_body(50211, "Edge TTS returned empty audio."),
        )

    media_type, extension = media_type_for(payload.format)
    headers = {
        "Content-Disposition": f'inline; filename="{req_id}.{extension}"',
        "Content-Length": str(len(audio_bytes)),
        "X-Request-ID": req_id,
        "X-TTS-Engine": payload.engine,
    }
    return StreamingResponse(io.BytesIO(audio_bytes), media_type=media_type, headers=headers)


# ------ POST /tts ------ 统一合成（引擎在请求体中指定）------
@app.post(
    "/tts",
    summary="TTS synthesis via edge engine",
    responses={
        200: {"description": "Binary MP3 audio stream."},
        401: {"model": ErrorResponse, "description": "API key authentication failed."},
        422: {"model": ErrorResponse, "description": "Invalid request body."},
        502: {"model": ErrorResponse, "description": "Edge TTS synthesis error."},
    },
)
async def text_to_speech(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return await _synthesize(payload)


# ------ POST /tts/edge ------ 引擎直连路由 ------
@app.post(
    "/tts/edge",
    summary="TTS synthesis via edge engine (direct URL)",
    responses={
        200: {"description": "Binary MP3 audio stream."},
        401: {"model": ErrorResponse, "description": "API key authentication failed."},
        422: {"model": ErrorResponse, "description": "Invalid request body."},
        502: {"model": ErrorResponse, "description": "Edge TTS synthesis error."},
    },
)
async def text_to_speech_edge(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    payload.engine = "edge"
    return await _synthesize(payload)


# ------ POST /text/ ------ 旧版兼容端点 ------
@app.post("/text/", include_in_schema=False)
async def legacy_text_to_speech(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return await _synthesize(payload)


@app.head("/text/", include_in_schema=False)
def legacy_text_to_speech_head() -> StreamingResponse:
    return tts_head()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
