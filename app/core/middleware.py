from __future__ import annotations

import uuid
import structlog # Changed from logging
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings

# Define a ContextVar to store the request_id for structured logging
request_id_context: ContextVar[str | None] = ContextVar("request_id_context", default=None)
telegram_id_context: ContextVar[int | None] = ContextVar("telegram_id_context", default=None)

logger = structlog.get_logger(__name__) # Changed to structlog

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request and response.
    Also stores the request_id in a ContextVar for structured logging.
    """
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Store request_id in ContextVar
        token = request_id_context.set(request_id)
        
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token) # Reset ContextVar after request
            
        response.headers["X-Request-ID"] = request_id
        return response


class BotAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate requests from the Telegram bot using X-Telegram-Secret.
    It also extracts X-Telegram-Id and stores it in request.state and a ContextVar.
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
                           path=request.url.path,
                           ip=request.client.host)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "unauthorized_bot", "message": "Invalid X-Telegram-Secret"}},
            )

        if not telegram_id_str:
            logger.warning("Unauthorized access attempt: Missing X-Telegram-Id",
                           path=request.url.path,
                           ip=request.client.host)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "unauthorized_bot", "message": "Missing X-Telegram-Id"}},
            )

        try:
            telegram_id = int(telegram_id_str)
            request.state.telegram_id = telegram_id
            # Store telegram_id in ContextVar
            token = telegram_id_context.set(telegram_id)
        except ValueError:
            logger.warning("Unauthorized access attempt: Invalid X-Telegram-Id format",
                           path=request.url.path,
                           telegram_id_str=telegram_id_str,
                           ip=request.client.host)
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "unauthorized_bot", "message": "Invalid X-Telegram-Id format"}},
            )
        
        try:
            response = await call_next(request)
        finally:
            telegram_id_context.reset(token) # Reset ContextVar after request

        return response
