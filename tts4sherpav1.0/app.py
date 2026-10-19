import io
import os
import sys
import traceback
import uuid
from typing import Any, Dict

import sherpa_onnx
import soundfile as sf
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
    media_type_for,
    register_error_handlers,
    require_startup_auth,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
require_startup_auth()

PORT = int(os.getenv("PORT", "8002"))
API_KEY = os.getenv("TTS_API_KEY", "my-fixed-key-2026").strip()
ENGINE_NAME = "sherpa"
SUPPORTED_ENGINES = frozenset({ENGINE_NAME, "offline"})
SUPPORTED_FORMATS = frozenset({"WAV"})
MAX_TEXT_LENGTH = int(os.getenv("TTS_MAX_TEXT_LENGTH", "1000"))

TTSRequest = create_tts_request_model(
    engine_default="sherpa",
    voice_default="0",
    format_default="WAV",
    supported_engines=SUPPORTED_ENGINES,
    supported_formats=SUPPORTED_FORMATS,
    max_text_length=MAX_TEXT_LENGTH,
)

# ---------------------------------------------------------------------------
# Sherpa ONNX model loading (startup)
# ---------------------------------------------------------------------------
matcha = sherpa_onnx.OfflineTtsMatchaModelConfig(
    acoustic_model="./matcha-icefall-zh-baker/model-steps-3.onnx",
    vocoder="./vocos-22khz-univ.onnx",
    lexicon="./matcha-icefall-zh-baker/lexicon.txt",
    tokens="./matcha-icefall-zh-baker/tokens.txt",
    data_dir="",
    dict_dir="./matcha-icefall-zh-baker/dict",
)

model = sherpa_onnx.OfflineTtsModelConfig(
    matcha=matcha,
    provider="cpu",
    debug=0,
    num_threads=int(os.getenv("TTS_NUM_THREADS", "10")),
)

tts_config = sherpa_onnx.OfflineTtsConfig(
    model=model,
    rule_fsts=(
        "./matcha-icefall-zh-baker/phone.fst,"
        "./matcha-icefall-zh-baker/date.fst,"
        "./matcha-icefall-zh-baker/number.fst"
    ),
    max_num_sentences=int(os.getenv("TTS_MAX_NUM_SENTENCES", "10")),
)

tts = sherpa_onnx.OfflineTts(tts_config)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sherpa Unified TTS API",
    version="1.0.0",
    description="Unified FastAPI HTTP interface for local sherpa_onnx TTS.",
)
register_error_handlers(app)
verify_api_key = create_verify_api_key(API_KEY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def resolve_sid(payload: TTSRequest) -> int:
    """Resolve speaker id: extra_params['sid'] > voice field > default 0."""
    if "sid" in payload.extra_params:
        return int(payload.extra_params["sid"])
    try:
        return int(payload.voice)
    except ValueError:
        return 0


def resolve_speed(payload: TTSRequest) -> float:
    """Resolve speed: extra_params['speed'] (backward compat) > top-level speed."""
    if "speed" in payload.extra_params:
        return float(payload.extra_params["speed"])
    return float(payload.speed)


def generate_audio(payload: TTSRequest) -> io.BytesIO:
    audio = tts.generate(
        payload.text,
        sid=resolve_sid(payload),
        speed=resolve_speed(payload),
    )
    audio_file = io.BytesIO()
    sf.write(
        audio_file,
        audio.samples,
        samplerate=audio.sample_rate,
        subtype="PCM_16",
        format="WAV",
    )
    audio_file.seek(0)
    return audio_file


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
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="preview.wav"'},
    )


def _synthesize(payload: TTSRequest) -> StreamingResponse:
    req_id = payload.req_id or uuid.uuid4().hex
    try:
        audio_file = generate_audio(payload)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_body(50001, "Local TTS engine failed.", str(exc)),
        ) from exc

    audio_size = audio_file.getbuffer().nbytes
    media_type, extension = media_type_for(payload.format)
    headers = {
        "Content-Disposition": f'inline; filename="{req_id}.{extension}"',
        "Content-Length": str(audio_size),
        "X-Request-ID": req_id,
        "X-TTS-Engine": payload.engine,
    }
    return StreamingResponse(audio_file, media_type=media_type, headers=headers)


# ------ POST /tts ------ 统一合成（引擎在请求体中指定）------
@app.post(
    "/tts",
    summary="Unified TTS synthesis",
    responses={
        200: {"description": "Binary WAV audio stream."},
        401: {"model": ErrorResponse, "description": "API key authentication failed."},
        422: {"model": ErrorResponse, "description": "Invalid request body."},
        500: {"model": ErrorResponse, "description": "Local TTS engine error."},
    },
)
def text_to_speech(
    payload: TTSRequest,
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    return _synthesize(payload)


# ------ POST /tts/{engine} ------ 引擎直连路由 ------
for _eng in sorted(SUPPORTED_ENGINES):
    def _make_route(engine_name: str):
        @app.post(
            f"/tts/{engine_name}",
            summary=f"TTS synthesis via {engine_name} engine (direct URL)",
            responses={
                200: {"description": "Binary WAV audio stream."},
                401: {"model": ErrorResponse, "description": "API key authentication failed."},
                422: {"model": ErrorResponse, "description": "Invalid request body."},
                500: {"model": ErrorResponse, "description": "Local TTS engine error."},
            },
        )
        def _engine_tts(
            payload: TTSRequest,
            _auth: None = Depends(verify_api_key),
            _eng_name: str = engine_name,
        ) -> StreamingResponse:
            payload.engine = _eng_name
            return _synthesize(payload)
        return _engine_tts
    _make_route(_eng)


# ------ POST /text/ ------ 旧版兼容端点 ------
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
    uvicorn.run(app, host="0.0.0.0", port=PORT)
