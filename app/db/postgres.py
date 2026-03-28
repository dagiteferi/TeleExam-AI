from __future__ import annotations
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None

Base = declarative_base()


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # Ensure driver is asyncpg even if psycopg2 is in .env for Alembic compatibility
        async_url = settings.sqlalchemy_database_url.replace("+psycopg2", "+asyncpg")
        _engine = create_async_engine(
            async_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        logger.info("Async DB engine initialized")
    return _engine


@asynccontextmanager
async def db_conn(*, telegram_id: int | None) -> AsyncIterator[AsyncConnection]:
    engine = get_engine()
    async with engine.connect() as conn:
        if telegram_id is not None:
            await conn.execute(
                text("select set_config('app.current_telegram_id', :tid, true)"),
                {"tid": str(telegram_id)},
            )
        yield conn

