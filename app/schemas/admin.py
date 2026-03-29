from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


class AdminUserResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    email: str
    role: str
    permissions: list[str] = []
    invited_by_email: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class InviteAdminRequest(BaseModel):
    email: str
    permissions: list[str] = []  # e.g. ["ban_user", "view_users", "view_stats"]


class InviteAdminResponse(BaseModel):
    email: str
    password: str  # Shown ONCE — superadmin must share securely
    permissions: list[str]
    message: str


class UserAdminUpdate(BaseModel):
    is_pro: bool | None = None
    plan_expiry: datetime | None = None
    is_banned: bool | None = None
    ban_reason: str | None = None


class DailyActiveUser(BaseModel):
    day: datetime
    dau: int

class DAUResponse(BaseModel):
    data: list[DailyActiveUser]

class TopInviter(BaseModel):
    user_id: UUID
    telegram_id: int
    telegram_username: str | None = None
    invite_count: int

class ReferralStatsResponse(BaseModel):
    top_inviters: list[TopInviter]

class ExamStatsResponse(BaseModel):
    total_exams: int
    total_users: int
    average_score: float

class QuestionStatsResponse(BaseModel):
    question_id: UUID
    prompt: str
    correct_answer_count: int
    total_answer_count: int
    accuracy: float

class UserFlaggedResponse(BaseModel):
    user_id: UUID
    telegram_id: int
    is_banned_pg: bool
    ban_reason_pg: str | None = None
    flag_redis: str | None = None # e.g., "blocked", "throttled"