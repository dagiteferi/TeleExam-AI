from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UserUpsertRequest(BaseModel):
    telegram_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    ref_code: UUID | None = None


class UserResponse(BaseModel):
    user_id: UUID
    telegram_id: int
    invite_code: UUID
    invite_count: int
    is_pro: bool
    plan_expiry: datetime | None = None
