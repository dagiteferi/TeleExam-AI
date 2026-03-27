from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncConnection
from redis.asyncio import Redis

from app.db.postgres import db_conn
from app.db.redis import get_redis_client as get_initialized_redis_client # Renamed to avoid conflict

telegram_secret_header = APIKeyHeader(name="X-Telegram-Secret", auto_error=False, scheme_name="TelegramSecret")
telegram_id_header = APIKeyHeader(name="X-Telegram-Id", auto_error=False, scheme_name="TelegramId")


async def get_current_telegram_id(request: Request) -> int:
    """
    Retrieves the telegram_id from the request state, which is set by BotAuthMiddleware.
    """
    telegram_id = request.state.telegram_id
    if not telegram_id:
        # This should ideally not happen if BotAuthMiddleware is correctly placed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Not authenticated"}},
        )
    return telegram_id


async def get_db_conn(
    telegram_id: Annotated[int, Depends(get_current_telegram_id)]
) -> AsyncConnection:
    """
    Provides an asynchronous database connection with the current telegram_id
    set for Row Level Security (RLS).
    """
    async with db_conn(telegram_id=telegram_id) as conn:
        yield conn


async def get_redis(
    redis_client: Annotated[Redis, Depends(get_initialized_redis_client)]
) -> Redis:
    """
    Provides an asynchronous Redis client.
    """
    return redis_client


CurrentTelegramId = Annotated[int, Depends(get_current_telegram_id)]
DbConn = Annotated[AsyncConnection, Depends(get_db_conn)]