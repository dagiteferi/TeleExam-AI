from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import validate_telegram_secret

logger = structlog.get_logger(__name__)

_SKIP_PATH_PREFIXES = ("/docs", "/openapi.json", "/health", "/api/health")


def _extract_telegram_id(request: Request, body_json: dict[str, Any] | None) -> int | None:
    header_id = request.headers.get("X-Telegram-Id")
    if header_id:
        try:
            return int(header_id)
        except ValueError:
            return None

    query_id = request.query_params.get("telegram_id")
    if query_id:
        try:
            return int(query_id)
        except ValueError:
            return None

    if body_json and "telegram_id" in body_json:
        try:
            return int(body_json["telegram_id"])
        except (TypeError, ValueError):
            return None

    return None


class TelegramAuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(_SKIP_PATH_PREFIXES):
            return await call_next(request)

        secret = request.headers.get("X-Telegram-Secret")
        if not validate_telegram_secret(secret):
            return JSONResponse(status_code=401, content={"success": False, "error": "Unauthorized"})

        body_json: dict[str, Any] | None = None
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                raw = await request.body()
                if raw:
                    body_json = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return JSONResponse(status_code=400, content={"success": False, "error": "Invalid JSON"})

            async def receive() -> dict[str, Any]:
                return {"type": "http.request", "body": raw, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]

        telegram_id = _extract_telegram_id(request, body_json)
        request.state.telegram_id = telegram_id

        response = await call_next(request)
        if telegram_id is not None:
            response.headers["X-Telegram-Id"] = str(telegram_id)
        return response

