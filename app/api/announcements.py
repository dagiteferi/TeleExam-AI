from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_public_db_conn
from app.core.config import settings
from app.models.announcement import Announcement, AnnouncementDelivery
from app.models.user import User
from app.schemas.announcement import DeliveryReport, PendingDelivery, SyncReport, SyncTask
from app.services.announcement_service import HAS_DUAL_ACCESS

# Used only by the bot's background sender (authenticated by the shared bot secret).
router = APIRouter(prefix="/announcements")


@router.get("/pending", response_model=list[PendingDelivery])
async def get_pending_deliveries(
    limit: int = 30,
    conn: AsyncConnection = Depends(get_public_db_conn),
) -> list[PendingDelivery]:
    """
    Next deliveries for the bot to send. Users skipped recently (busy, or a temporary
    error) go to the back of the queue so they don't block everyone else.
    """
    rows = await conn.execute(
        select(
            AnnouncementDelivery.id.label("delivery_id"),
            User.telegram_id,
            Announcement.text,
            Announcement.version,
            User.department_id.isnot(None).label("has_department"),
            User.is_pro,
            case((HAS_DUAL_ACCESS, True), else_=False).label("has_dual_access"),
        )
        .join(Announcement, AnnouncementDelivery.announcement_id == Announcement.id)
        .join(User, AnnouncementDelivery.user_id == User.id)
        .where(
            AnnouncementDelivery.status == "pending",
            User.is_banned.isnot(True),
            Announcement.deleted_at.is_(None),
            # Only this backend's bot: local and production share the database.
            Announcement.bot_id.is_not_distinct_from(settings.telegram_bot_id),
        )
        .order_by(AnnouncementDelivery.last_attempt_at.asc().nulls_first(), AnnouncementDelivery.created_at.asc())
        .limit(min(limit, 100))
    )
    return [PendingDelivery(**row) for row in rows.mappings()]


@router.post("/deliveries/report")
async def report_deliveries(
    report: DeliveryReport,
    conn: AsyncConnection = Depends(get_public_db_conn),
) -> dict:
    """The bot reports which deliveries were sent, deferred (try later) or failed for good."""
    now = datetime.datetime.now(datetime.timezone.utc)
    pending = AnnouncementDelivery.status == "pending"
    # "cancelled" too: the admin may stop or delete it while the bot is mid-send. Recording
    # the copy as sent (with its message id) lets a delete still remove it from the chat.
    sendable = AnnouncementDelivery.status.in_(("pending", "cancelled"))
    for item in report.sent_messages:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id == item.delivery_id, sendable)
            .values(
                status="sent",
                message_id=item.message_id,
                text_version=item.version,
                sent_at=now,
                last_attempt_at=now,
                attempts=AnnouncementDelivery.attempts + 1,
            )
        )
    if report.sent:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id.in_(report.sent), sendable)
            .values(
                status="sent",
                sent_at=now,
                last_attempt_at=now,
                attempts=AnnouncementDelivery.attempts + 1,
            )
        )
    if report.deferred:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id.in_(report.deferred), pending)
            .values(last_attempt_at=now, attempts=AnnouncementDelivery.attempts + 1)
        )
    for failure in report.failed:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id == failure.delivery_id, pending)
            .values(
                status="failed",
                error=failure.error,
                last_attempt_at=now,
                attempts=AnnouncementDelivery.attempts + 1,
            )
        )
    await conn.commit()
    return {"ok": True}


@router.get("/sync", response_model=list[SyncTask])
async def get_sync_tasks(
    limit: int = 30,
    conn: AsyncConnection = Depends(get_public_db_conn),
) -> list[SyncTask]:
    """
    Delivered copies the bot must change in users' chats: edit them to the latest
    text, or delete them because the admin deleted the announcement.
    """
    limit = min(limit, 100)
    base = (
        select(
            AnnouncementDelivery.id.label("delivery_id"),
            User.telegram_id,
            AnnouncementDelivery.message_id,
            Announcement.text,
            Announcement.version,
            Announcement.deleted_at,
        )
        .join(Announcement, AnnouncementDelivery.announcement_id == Announcement.id)
        .join(User, AnnouncementDelivery.user_id == User.id)
        .where(
            AnnouncementDelivery.status == "sent",
            AnnouncementDelivery.message_id.isnot(None),
            Announcement.bot_id.is_not_distinct_from(settings.telegram_bot_id),
        )
        .order_by(AnnouncementDelivery.last_attempt_at.asc().nulls_first())
        .limit(limit)
    )
    deletes = (await conn.execute(base.where(Announcement.deleted_at.isnot(None)))).mappings().all()
    edits = (
        await conn.execute(
            base.where(
                Announcement.deleted_at.is_(None),
                AnnouncementDelivery.text_version < Announcement.version,
            )
        )
    ).mappings().all()
    tasks = [
        SyncTask(
            delivery_id=row["delivery_id"],
            action="delete",
            telegram_id=row["telegram_id"],
            message_id=row["message_id"],
            version=row["version"],
        )
        for row in deletes
    ] + [
        SyncTask(
            delivery_id=row["delivery_id"],
            action="edit",
            telegram_id=row["telegram_id"],
            message_id=row["message_id"],
            text=row["text"],
            version=row["version"],
        )
        for row in edits
    ]
    return tasks[:limit]


@router.post("/sync/report")
async def report_sync(
    report: SyncReport,
    conn: AsyncConnection = Depends(get_public_db_conn),
) -> dict:
    """The bot reports which delivered copies it edited, deleted, or could not change."""
    now = datetime.datetime.now(datetime.timezone.utc)
    sent = AnnouncementDelivery.status == "sent"
    for item in report.edited:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id == item.delivery_id, sent)
            .values(text_version=item.version, last_attempt_at=now, error=None)
        )
    if report.deleted:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id.in_(report.deleted), sent)
            .values(status="deleted", message_id=None, last_attempt_at=now)
        )
    if report.deferred:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id.in_(report.deferred), sent)
            .values(last_attempt_at=now)
        )
    for failure in report.failed:
        # Permanent (chat gone, message too old...): stop trying for this copy.
        values = {"error": failure.error, "last_attempt_at": now}
        if failure.action == "edit":
            values["text_version"] = failure.version
        else:
            values["message_id"] = None
        await conn.execute(
            update(AnnouncementDelivery).where(AnnouncementDelivery.id == failure.delivery_id, sent).values(**values)
        )
    await conn.commit()
    return {"ok": True}
