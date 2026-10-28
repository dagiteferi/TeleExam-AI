from __future__ import annotations
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import event, exc
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None

Base = declarative_base()

# Connections idle longer than this are pinged before reuse; busier ones are trusted.
_PING_IF_IDLE_SECONDS = 60


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        async_url = settings.sqlalchemy_database_url.replace("+psycopg2", "+asyncpg")
        _engine = create_async_engine(
            async_url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
        )
        _ping_idle_connections(_engine)
        logger.info("Async DB engine initialized")
    return _engine


def _ping_idle_connections(engine: AsyncEngine) -> None:
    """
    pool_pre_ping costs a full DB round trip on every request. Only ping connections
    that sat idle long enough for the pooler to have dropped them.
    """
    @event.listens_for(engine.sync_engine, "checkin")
    def _on_checkin(dbapi_connection, connection_record):
        connection_record.info["checked_in_at"] = time.monotonic()

    @event.listens_for(engine.sync_engine, "checkout")
    def _on_checkout(dbapi_connection, connection_record, connection_proxy):
        checked_in_at = connection_record.info.get("checked_in_at")
        if checked_in_at is None or time.monotonic() - checked_in_at < _PING_IF_IDLE_SECONDS:
            return
        try:
            dbapi_connection.ping()
        except Exception as e:
            # Makes the pool discard this connection and hand out a fresh one
            raise exc.DisconnectionError() from e


@asynccontextmanager
async def db_conn(*, telegram_id: int | None, read_only: bool = False) -> AsyncIterator[AsyncConnection]:
    # telegram_id used to be sent as app.current_telegram_id for RLS, but no policy reads it
    # and the backend role bypasses RLS, so it was a wasted round trip on every request.
    engine = get_engine()
    async with engine.connect() as conn:
        if read_only:
            # Autocommit skips the BEGIN and ROLLBACK round trips around each request.
            # Only for requests that never write: there is no transaction to roll back.
            await conn.execution_options(isolation_level="AUTOCOMMIT")
        yield conn

