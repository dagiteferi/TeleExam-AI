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
    department_id: UUID | None = None



class DualDepartmentRequest(BaseModel):
    department_id: UUID


class ActiveDepartmentRequest(BaseModel):
    department_id: UUID


class UserResponse(BaseModel):
    user_id: UUID
    telegram_id: int
    invite_code: UUID
    invite_count: int
    is_pro: bool
    is_full_access: bool = False
    plan_expiry: datetime | None = None
    department_id: UUID | None = None
    department_name: str | None = None
    secondary_department_id: UUID | None = None
    secondary_department_name: str | None = None
    secondary_department_unlocked: bool = False
    # True when the second department is usable (PRO + approved dual fee, or full access)
    has_dual_access: bool = False
    # Department currently being studied (the main one unless switched)
    active_department_id: UUID | None = None
    active_department_name: str | None = None
