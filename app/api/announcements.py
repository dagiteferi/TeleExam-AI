from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_public_db_conn
from app.core.config import settings
from app.models.announcement import Announcement, AnnouncementDelivery
from app.models.user import User
from app.schemas.announcement import DeliveryReport, PendingDelivery
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
            User.department_id.isnot(None).label("has_department"),
            User.is_pro,
            case((HAS_DUAL_ACCESS, True), else_=False).label("has_dual_access"),
        )
        .join(Announcement, AnnouncementDelivery.announcement_id == Announcement.id)
        .join(User, AnnouncementDelivery.user_id == User.id)
        .where(
            AnnouncementDelivery.status == "pending",
            User.is_banned.isnot(True),
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
    if report.sent:
        await conn.execute(
            update(AnnouncementDelivery)
            .where(AnnouncementDelivery.id.in_(report.sent), pending)
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
