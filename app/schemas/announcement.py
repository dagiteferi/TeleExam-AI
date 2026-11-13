from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Audience = Literal["all", "pro", "free", "dual", "department", "users"]

# Telegram allows 4096 characters; leave room for the "📢 Announcement" header.
MAX_ANNOUNCEMENT_LENGTH = 3500
# For bigger groups, use an audience (all, PRO, department...) instead of picking users.
MAX_SELECTED_USERS = 500


class AnnouncementAudience(BaseModel):
    audience: Audience
    department_id: UUID | None = None  # audience == "department"
    user_ids: list[UUID] | None = None  # audience == "users": users picked in the admin panel

    @model_validator(mode="after")
    def _check_target(self):
        if self.audience == "department" and not self.department_id:
            raise ValueError("Choose a department.")
        if self.audience == "users":
            if not self.user_ids:
                raise ValueError("Select at least one user.")
            if len(set(self.user_ids)) > MAX_SELECTED_USERS:
                raise ValueError(f"Select at most {MAX_SELECTED_USERS} users, or send to a group instead.")
        return self


class AnnouncementCreate(AnnouncementAudience):
    text: str = Field(min_length=1, max_length=MAX_ANNOUNCEMENT_LENGTH)


class AnnouncementUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ANNOUNCEMENT_LENGTH)


class AnnouncementPreview(BaseModel):
    recipient_count: int


class AnnouncementResponse(BaseModel):
    id: UUID
    text: str
    # Plain str, not Audience: one old or unknown row must never break the whole list.
    audience: str
    department_id: UUID | None = None
    department_name: str | None = None
    target_user_id: UUID | None = None
    target_user_label: str | None = None  # name when one user was selected
    created_by: str | None = None
    created_at: datetime
    recipient_count: int
    sent_count: int = 0
    pending_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    version: int = 1  # 1 = never edited
    # Delivered copies the bot is still updating to the latest text
    updating_count: int = 0
    # Delivered before message ids were recorded: can't be edited or deleted in the chat
    untracked_count: int = 0


class DeleteResult(BaseModel):
    # Delivered copies the bot will now remove from users' chats
    removing_count: int
    # Delivered copies that can't be removed (sent before message ids were recorded)
    untracked_count: int


class DeliveryRow(BaseModel):
    """One recipient of an announcement, for the admin's delivery details."""
    user_id: UUID
    name: str
    telegram_username: str | None = None
    telegram_id: int
    status: str  # pending, sent, failed, cancelled
    attempts: int
    last_attempt_at: datetime | None = None
    sent_at: datetime | None = None
    error: str | None = None


# ── Bot delivery queue ───────────────────────────────────────────────────────

class PendingDelivery(BaseModel):
    delivery_id: UUID
    telegram_id: int
    text: str
    # What the bot needs to attach the user's correct main menu
    has_department: bool
    is_pro: bool
    has_dual_access: bool
    version: int = 1  # version of the text, reported back once sent


class SentDelivery(BaseModel):
    delivery_id: UUID
    message_id: int
    version: int = 1


class FailedDelivery(BaseModel):
    delivery_id: UUID
    error: str = Field(max_length=500)


class DeliveryReport(BaseModel):
    sent: list[UUID] = []  # older bots: no message id
    sent_messages: list[SentDelivery] = []
    deferred: list[UUID] = []  # user was busy (exam, AI chat, ...) or a temporary error
    failed: list[FailedDelivery] = []  # permanent (user blocked the bot, chat not found)


# ── Bot edit / delete queue (copies already in users' chats) ─────────────────

class SyncTask(BaseModel):
    delivery_id: UUID
    action: Literal["edit", "delete"]
    telegram_id: int
    message_id: int
    text: str | None = None  # edit only
    version: int


class EditedDelivery(BaseModel):
    delivery_id: UUID
    version: int


class FailedSync(BaseModel):
    delivery_id: UUID
    action: Literal["edit", "delete"]
    version: int
    error: str = Field(max_length=500)


class SyncReport(BaseModel):
    edited: list[EditedDelivery] = []
    deleted: list[UUID] = []
    deferred: list[UUID] = []  # temporary error: try again later
    failed: list[FailedSync] = []  # permanent: stop trying for this copy
