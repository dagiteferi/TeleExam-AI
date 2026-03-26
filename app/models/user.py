from __future__ import annotations

from pydantic import BaseModel


class UserUpsertRequest(BaseModel):
    telegram_id: int


class UserUpsertResponse(BaseModel):
    success: bool = True
    user_id: int
    pro_status: bool

