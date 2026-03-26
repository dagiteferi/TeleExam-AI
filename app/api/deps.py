from __future__ import annotations
from fastapi import Depends, HTTPException, Request


def get_current_telegram_id(request: Request) -> int:
    telegram_id = getattr(request.state, "telegram_id", None)
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="telegram_id is required")
    if not isinstance(telegram_id, int):
        raise HTTPException(status_code=400, detail="telegram_id must be an integer")
    return telegram_id


CurrentTelegramId = Depends(get_current_telegram_id)

