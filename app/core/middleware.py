from __future__ import annotations

import datetime
import hmac
import json
import re
import time
import uuid
import structlog
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings
from sqlalchemy import text

from app.db.postgres import get_engine
from app.db.redis import (
    get_redis_client,
    get_rate_limit_key,
    get_ban_cache_key,
    BAN_CACHE_TTL_SECONDS,
)

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
        if request.url.path in ["/docs", "/openapi.json", "/metrics"] or request.url.path.startswith("/admin") or request.url.path.startswith("/api/v1/render") or request.url.path.startswith("/api/public"):
            return await call_next(request)

        telegram_secret = request.headers.get("X-Telegram-Secret")
        telegram_id_str = request.headers.get("X-Telegram-Id")

        if not telegram_secret or not hmac.compare_digest(telegram_secret.encode(), settings.telegram_webhook_secret.encode()):
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
            ban = await _get_ban_status(telegram_id)
            if ban is not None:
                logger.info("Blocked request from banned user", path=request.url.path)
                return JSONResponse(
                    status_code=403,
                    content={"error": {
                        "code": "user_banned",
                        "message": "Your account has been restricted by an administrator.",
                        "reason": ban.get("reason"),
                        "banned_until": ban.get("until"),
                    }},
                )
            response = await call_next(request)
        finally:
            telegram_id_context.reset(token)

        return response


async def _get_ban_status(telegram_id: int) -> dict | None:
    """Returns {"reason", "until"} if the user is currently banned, else None.

    Cached in Redis for a short time so every request doesn't hit Postgres;
    admin ban/unban endpoints delete the cache key so changes apply immediately.
    """
    cache_key = get_ban_cache_key(telegram_id)
    redis = None
    try:
        redis = await get_redis_client()
        cached = await redis.get(cache_key)
        if cached is not None:
            ban = json.loads(cached)
            if ban is None:
                return None
            until = ban.get("until")
            if until is None or datetime.datetime.fromisoformat(until) > datetime.datetime.now(datetime.timezone.utc):
                return ban
            # cached temporary ban has expired: fall through and re-check the DB
    except Exception:
        logger.exception("Ban cache unavailable, checking database")
        redis = None

    now = datetime.datetime.now(datetime.timezone.utc)
    async with get_engine().connect() as conn:
        row = (await conn.execute(
            text("select is_banned, ban_reason, banned_until from users where telegram_id = :tid"),
            {"tid": telegram_id},
        )).first()

        ban = None
        if row is not None and row.is_banned:
            if row.banned_until is not None and row.banned_until <= now:
                # Temporary ban has run out: lift it
                await conn.execute(
                    text("update users set is_banned = false, ban_reason = null, banned_until = null "
                         "where telegram_id = :tid and banned_until <= :now"),
                    {"tid": telegram_id, "now": now},
                )
                await conn.commit()
            else:
                ban = {
                    "reason": row.ban_reason,
                    "until": row.banned_until.isoformat() if row.banned_until else None,
                }

    if redis is not None:
        try:
            await redis.set(cache_key, json.dumps(ban), ex=BAN_CACHE_TTL_SECONDS)
        except Exception:
            logger.exception("Failed to cache ban status")
    return ban


# UUIDs and numeric IDs in a path, e.g. /api/sessions/3f2a.../answer -> /api/sessions/{id}/answer
_ID_SEGMENT = re.compile(r"/(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\d+)(?=/|$)")


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in ["/docs", "/openapi.json", "/metrics"] or request.url.path.startswith("/admin") or request.url.path.startswith("/api/v1/render") or request.url.path.startswith("/api/public"):
            return await call_next(request)

        telegram_id = getattr(request.state, "telegram_id", None)
        if not telegram_id:
            return await call_next(request)

        redis = await get_redis_client()
        now = time.time()
        window_start = now - settings.rate_limit_window_seconds

        # One bucket per user per route, with IDs collapsed so /sessions/<id>/answer
        # shares a bucket across sessions instead of getting a fresh one each time.
        route_identifier = _ID_SEGMENT.sub("/{id}", request.url.path)
        rate_limit_key = get_rate_limit_key(telegram_id, route_identifier)

        async with redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(rate_limit_key, 0, window_start)
            pipe.zadd(rate_limit_key, {str(uuid.uuid4()): now})
            pipe.zcard(rate_limit_key)
            pipe.expire(rate_limit_key, settings.rate_limit_window_seconds + 60)
            _, _, request_count, _ = await pipe.execute()

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

        return await call_next(request)
