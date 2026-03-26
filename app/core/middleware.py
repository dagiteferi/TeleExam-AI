from __future__ import annotations

import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request and response.
    """
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class BotAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate requests from the Telegram bot using X-Telegram-Secret.
    It also extracts X-Telegram-Id and stores it in request.state.
    """
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip authentication for /docs and /openapi.json paths
        if request.url.path in ["/docs", "/openapi.json", "/metrics"]:
            return await call_next(request)

        telegram_secret = request.headers.get("X-Telegram-Secret")
        telegram_id_str = request.headers.get("X-Telegram-Id")

        if not telegram_secret or telegram_secret != settings.TELEGRAM_SHARED_SECRET:
            logger.warning("Unauthorized access attempt: Invalid X-Telegram-Secret",
                           request_id=getattr(request.state, "request_id", "N/A"),
                           path=request.url.path,
                           ip=request.client.host)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "unauthorized_bot", "message": "Invalid X-Telegram-Secret"}},
            )

        if not telegram_id_str:
            logger.warning("Unauthorized access attempt: Missing X-Telegram-Id",
                           request_id=getattr(request.state, "request_id", "N/A"),
                           path=request.url.path,
                           ip=request.client.host)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "unauthorized_bot", "message": "Missing X-Telegram-Id"}},
            )

        try:
            telegram_id = int(telegram_id_str)
            request.state.telegram_id = telegram_id
        except ValueError:
            logger.warning("Unauthorized access attempt: Invalid X-Telegram-Id format",
                           request_id=getattr(request.state, "request_id", "N/A"),
                           path=request.url.path,
                           telegram_id_str=telegram_id_str,
                           ip=request.client.host)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "unauthorized_bot", "message": "Invalid X-Telegram-Id format"}},
            )

        return await call_next(request)