"""
TTS Common — shared models, error handling, auth, and utilities
for all TTS microservices in this repository.

Usage in each service's app.py:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from tts_common import (
        create_tts_request_model, ErrorResponse, EngineInfo,
        error_body, register_error_handlers, create_verify_api_key,
        media_type_for, pitch_to_ssml, volume_to_ssml, speed_to_rate,
    )
"""

from .models import ErrorResponse, EngineInfo, create_tts_request_model
from .errors import error_body, register_error_handlers
from .auth import create_verify_api_key
from .startup_auth import require_startup_auth
from .utils import media_type_for, pitch_to_ssml, volume_to_ssml, speed_to_rate

__all__ = [
    "create_tts_request_model",
    "ErrorResponse",
    "EngineInfo",
    "error_body",
    "register_error_handlers",
    "create_verify_api_key",
    "require_startup_auth",
    "media_type_for",
    "pitch_to_ssml",
    "volume_to_ssml",
    "speed_to_rate",
]
