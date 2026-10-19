"""Shared authentication dependency for TTS services."""

import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from .errors import error_body
from .startup_auth import _startup_tokens


def create_verify_api_key(api_key: str):
    """Return a FastAPI dependency that checks the X-API-Key header.

    Accepts either:
    - The fixed TTS_API_KEY (if configured via environment variable)
    - The session token generated at startup login

    If neither is configured/available, auth is skipped.
    Raises HTTPException(401) with unified error format on failure.
    """

    async def verify(x_api_key: Optional[str] = Header(None)) -> None:
        # 收集所有有效 token
        valid_tokens = set(_startup_tokens)
        if api_key:
            valid_tokens.add(api_key)

        if not x_api_key or x_api_key not in valid_tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_body(40100, "Missing or invalid API key."),
            )

    return verify
