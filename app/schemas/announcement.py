from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Audience = Literal["all", "pro", "free", "dual", "department", "user"]

# Telegram allows 4096 characters; leave room for the "📢 Announcement" header.
MAX_ANNOUNCEMENT_LENGTH = 3500


class AnnouncementAudience(BaseModel):
    audience: Audience
    department_id: UUID | None = None  # audience == "department"
    telegram_id: int | None = None  # audience == "user"

    @model_validator(mode="after")
    def _check_target(self):
        if self.audience == "department" and not self.department_id:
            raise ValueError("Choose a department.")
        if self.audience == "user" and not self.telegram_id:
            raise ValueError("Enter the user's Telegram ID.")
        return self


class AnnouncementCreate(AnnouncementAudience):
    text: str = Field(min_length=1, max_length=MAX_ANNOUNCEMENT_LENGTH)


class AnnouncementPreview(BaseModel):
    recipient_count: int


class AnnouncementResponse(BaseModel):
    id: UUID
    text: str
    audience: Audience
    department_id: UUID | None = None
    department_name: str | None = None
    target_user_id: UUID | None = None
    target_user_label: str | None = None
    created_by: str | None = None
    created_at: datetime
    recipient_count: int
    sent_count: int = 0
    pending_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0


# ── Bot delivery queue ───────────────────────────────────────────────────────

class PendingDelivery(BaseModel):
    delivery_id: UUID
    telegram_id: int
    text: str
    # What the bot needs to attach the user's correct main menu
    has_department: bool
    is_pro: bool
    has_dual_access: bool


class FailedDelivery(BaseModel):
    delivery_id: UUID
    error: str = Field(max_length=500)


class DeliveryReport(BaseModel):
    sent: list[UUID] = []
    deferred: list[UUID] = []  # user was busy (exam, AI chat, ...) or a temporary error
    failed: list[FailedDelivery] = []  # permanent (user blocked the bot, chat not found)
