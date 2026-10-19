"""Shared error utilities for TTS services."""

import json
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_body(code: int, message: str, details: Any = None) -> Dict[str, Any]:
    """Return the unified error JSON structure."""
    return {"code": code, "message": message, "details": details}


def _sanitize_errors(errors: List[Any]) -> List[Dict[str, Any]]:
    """Convert Pydantic v2 validation errors to JSON-safe dicts.

    Pydantic v2 error details may contain non-serializable objects (e.g. ValueError
    in ctx['error']). This converts them to strings.
    """
    # Use Pydantic's own JSON serialization, then parse back
    try:
        return json.loads(json.dumps(errors, default=str))
    except (TypeError, ValueError):
        return [str(e) for e in errors]


def register_error_handlers(app: FastAPI) -> None:
    """Register HTTPException and RequestValidationError handlers on `app`.

    Transforms native FastAPI errors into the unified {code, message, details} format.
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and {"code", "message"}.issubset(detail):
            body = error_body(
                int(detail["code"]),
                str(detail["message"]),
                detail.get("details"),
            )
        else:
            body = error_body(exc.status_code * 100, str(detail))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body(42200, "Invalid request body.", _sanitize_errors(exc.errors())),
        )
