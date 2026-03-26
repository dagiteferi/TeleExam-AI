from __future__ import annotations
from collections.abc import AsyncIterator
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncConnection
from app.db.postgres import db_conn


def get_current_telegram_id(request: Request) -> int:
    telegram_id = getattr(request.state, "telegram_id", None)
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="telegram_id is required")
    if not isinstance(telegram_id, int):
        raise HTTPException(status_code=400, detail="telegram_id must be an integer")
    return telegram_id


CurrentTelegramId = Depends(get_current_telegram_id)


async def get_db_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    telegram_id = getattr(request.state, "telegram_id", None)
    async with db_conn(telegram_id=telegram_id) as conn:
        yield conn


DbConn = Depends(get_db_conn)

