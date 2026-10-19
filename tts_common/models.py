"""Shared Pydantic models for TTS services.

The core piece is `create_tts_request_model()`, a factory function that returns
a TTSRequest BaseModel subclass customized for a specific service's supported
engines, formats, and defaults. This avoids code duplication while allowing each
service to enforce its own constraints.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator, validator


class ErrorResponse(BaseModel):
    """统一的错误响应格式。"""
    code: int = Field(..., description="业务错误码")
    message: str = Field(..., description="错误描述信息")
    details: Any = Field(None, description="错误详情")


class EngineInfo(BaseModel):
    """引擎信息，由 GET /tts/engines 返回。"""
    name: str
    type: str = "remote"
    formats: List[str] = []
    sample_rates: Optional[List[int]] = None
    description: str = ""


def create_tts_request_model(
    engine_default: str,
    voice_default: str,
    format_default: str,
    supported_engines: frozenset,
    supported_formats: frozenset,
    max_text_length: Optional[int] = None,
) -> type:
    """Create a TTSRequest Pydantic model customized for a specific service.

    Args:
        engine_default: Default engine name.
        voice_default: Default voice identifier.
        format_default: Default audio format (e.g. 'MP3', 'WAV').
        supported_engines: Allowed engine names (lowercase).
        supported_formats: Allowed audio formats (uppercase).
        max_text_length: If set, text longer than this will be rejected.

    Returns:
        A Pydantic BaseModel subclass ready for use as a FastAPI request body.
    """
    _engines = supported_engines
    _formats = supported_formats
    _max_len = max_text_length

    class TTSRequest(BaseModel):
        text: str = Field(..., min_length=1, description="待合成的文本内容（必填）。")
        voice: str = Field(voice_default, min_length=1, description="语音角色或说话人标识，默认值见各引擎说明。")
        format: str = Field(format_default, description="音频输出格式（MP3/WAV/FLAC），默认值见各引擎说明。")
        engine: str = Field(engine_default, description="TTS 引擎名称，默认值见各引擎说明。")
        req_id: Optional[str] = Field(None, description="请求追踪 ID，不传则自动生成 UUID。")
        extra_params: Dict[str, Any] = Field(
            default_factory=dict,
            description="引擎特有附加参数。",
        )
        speed: float = Field(1.0, ge=0.5, le=2.0, description="语速倍数（1.0=正常，1.2=增强 20%，0.8=减弱 20%）。")
        pitch: float = Field(1.0, ge=0.5, le=2.0, description="音调倍数（1.0=正常，1.2=提高 20%，0.8=降低 20%）。")
        style: str = Field("general", description="语音风格，如 cheerful/sad/angry。")
        volume: float = Field(1.0, ge=0.0, le=3.0, description="音量倍数（1.0=正常，1.2=增强 20%，0.8=减弱 20%）。")
        sample_rate: Optional[int] = Field(
            16000,
            description="音频采样率（Hz），默认 16000。可选 8000/16000/22050/24000/32000/44100/48000。",
        )

        @model_validator(mode="before")
        @classmethod
        def accept_legacy_input(cls, values: Any) -> Any:
            """Accept 'input' as an alias for 'text' for backward compatibility."""
            if isinstance(values, dict):
                if "text" not in values and "input" in values:
                    values["text"] = values["input"]
            return values

        @validator("text")
        def validate_text(cls, value: str) -> str:
            text = value.strip()
            if not text:
                raise ValueError("text cannot be empty")
            if _max_len is not None and len(text) > _max_len:
                raise ValueError(f"text length must be <= {_max_len}")
            return text

        @validator("format")
        def normalize_format(cls, value: str) -> str:
            audio_format = value.strip().upper()
            if audio_format not in _formats:
                raise ValueError(
                    f"format must be one of: {', '.join(sorted(_formats))}"
                )
            return audio_format

        @validator("engine")
        def normalize_engine(cls, value: str) -> str:
            engine = value.strip().lower()
            if engine not in _engines:
                raise ValueError(
                    f"engine must be one of: {', '.join(sorted(_engines))}"
                )
            return engine

        @validator("sample_rate")
        def check_sample_rate(cls, value: Optional[int]) -> Optional[int]:
            if value is not None and value not in (8000, 16000, 22050, 24000, 32000, 44100, 48000):
                raise ValueError(
                    "sample_rate must be one of: 8000, 16000, 22050, 24000, 32000, 44100, 48000"
                )
            return value

    return TTSRequest
