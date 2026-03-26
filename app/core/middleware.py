from __future__ import annotations

import time
import uuid
import structlog
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings
from app.db.redis import get_redis_client, get_rate_limit_key

request_id_context: ContextVar[str | None] = ContextVar("request_id_context", default=None)
telegram_id_context: ContextVar[int | None] = ContextVar("telegram_id_context", default=None)

logger = structlog.get_logger(__name__)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        token = request_id_context.set(request_id)
        
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
            
        response.headers["X-Request-ID"] = request_id
        return response


class BotAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in ["/docs", "/openapi.json", "/metrics"]:
            return await call_next(request)

        telegram_secret = request.headers.get("X-Telegram-Secret")
        telegram_id_str = request.headers.get("X-Telegram-Id")

        if not telegram_secret or telegram_secret != settings.telegram_webhook_secret:
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
            telegram_id_context.reset(token)

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in ["/docs", "/openapi.json", "/metrics"]:
            return await call_next(request)

        telegram_id = request.state.get("telegram_id")
        if not telegram_id:
            return await call_next(request)

        redis = await get_redis_client()
        current_time = int(time.time())
        
        route_identifier = request.url.path 
        rate_limit_key = get_rate_limit_key(telegram_id, route_identifier)

        await redis.zadd(rate_limit_key, {str(uuid.uuid4()): current_time})
        
        window_start = current_time - settings.rate_limit_window_seconds
        await redis.zremrangebyscore(rate_limit_key, 0, window_start)
        
        request_count = await redis.zcard(rate_limit_key)

        if request_count > settings.rate_limit_requests:
            logger.warning("Rate limit exceeded",
                           telegram_id=telegram_id,
                           path=request.url.path,
                           request_count=request_count,
                           limit=settings.rate_limit_requests)
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "Too Many Requests"}},
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )
        
        await redis.expire(rate_limit_key, settings.rate_limit_window_seconds + 60)

        return await call_next(request)
