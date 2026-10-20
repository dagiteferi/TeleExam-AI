from __future__ import annotations

import datetime
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.admin.deps import get_admin_db, require_superadmin
from app.core.config import settings
from app.core.utils import display_name
from app.models.announcement import Announcement, AnnouncementDelivery
from app.models.department import Department
from app.models.user import User
from app.schemas.announcement import (
    AnnouncementAudience,
    AnnouncementCreate,
    AnnouncementPreview,
    AnnouncementResponse,
)
from app.services.announcement_service import audience_filter

router = APIRouter(prefix="/announcements", dependencies=[Depends(require_superadmin)])


async def _check_target(conn: AsyncConnection, target: AnnouncementAudience) -> UUID | None:
    """Validates the department / selected users; returns the user's id when exactly one is selected."""
    if target.audience == "department":
        exists = await conn.scalar(select(Department.id).where(Department.id == target.department_id))
        if not exists:
            raise HTTPException(status_code=404, detail="Department not found")
    if target.audience == "users":
        selected = set(target.user_ids or [])
        found = await conn.scalar(select(func.count(User.id)).where(User.id.in_(selected)))
        if found != len(selected):
            raise HTTPException(status_code=404, detail="Some selected users no longer exist. Refresh and try again.")
        return next(iter(selected)) if len(selected) == 1 else None
    return None


@router.post("/preview", response_model=AnnouncementPreview)
async def preview_announcement(
    target: AnnouncementAudience,
    conn: AsyncConnection = Depends(get_admin_db),
) -> AnnouncementPreview:
    """How many users an announcement to this audience would reach."""
    await _check_target(conn, target)
    count = await conn.scalar(select(func.count(User.id)).where(audience_filter(target)))
    return AnnouncementPreview(recipient_count=count or 0)


@router.post("", response_model=AnnouncementResponse)
async def create_announcement(
    body: AnnouncementCreate,
    admin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> AnnouncementResponse:
    """
    Queues an announcement for every matching user. The bot delivers it in the
    background; users in an exam, AI chat or other flow get it once they are idle.
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="The message is empty.")
    target_user_id = await _check_target(conn, body)

    announcement_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    await conn.execute(
        insert(Announcement).values(
            id=announcement_id,
            text=text,
            audience=body.audience,
            department_id=body.department_id if body.audience == "department" else None,
            target_user_id=target_user_id,
            bot_id=settings.telegram_bot_id,
            created_by=admin.get("email"),
            recipient_count=0,
            created_at=now,
        )
    )
    # One pending delivery per matching user, created in a single statement.
    result = await conn.execute(
        insert(AnnouncementDelivery).from_select(
            ["id", "announcement_id", "user_id", "status", "attempts", "created_at"],
            select(
                func.gen_random_uuid(),
                literal(announcement_id),
                User.id,
                literal("pending"),
                literal(0),
                literal(now),
            ).where(audience_filter(body)),
        )
    )
    recipient_count = result.rowcount or 0
    if recipient_count == 0:
        await conn.rollback()
        raise HTTPException(status_code=400, detail="No users match this audience, so nothing was sent.")

    await conn.execute(
        update(Announcement).where(Announcement.id == announcement_id).values(recipient_count=recipient_count)
    )
    await conn.commit()
    return (await _list(conn, announcement_id=announcement_id))[0]


@router.get("", response_model=list[AnnouncementResponse])
async def list_announcements(
    limit: int = 50,
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[AnnouncementResponse]:
    """Recent announcements with how many were sent, are waiting, or failed."""
    return await _list(conn, limit=min(limit, 200))


@router.post("/{announcement_id}/cancel", response_model=AnnouncementResponse)
async def cancel_announcement(
    announcement_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> AnnouncementResponse:
    """Stops delivery to users who have not received it yet. Already-sent messages stay."""
    exists = await conn.scalar(
        select(Announcement.id).where(
            Announcement.id == announcement_id,
            Announcement.bot_id.is_not_distinct_from(settings.telegram_bot_id),
        )
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await conn.execute(
        update(AnnouncementDelivery)
        .where(AnnouncementDelivery.announcement_id == announcement_id, AnnouncementDelivery.status == "pending")
        .values(status="cancelled")
    )
    await conn.commit()
    return (await _list(conn, announcement_id=announcement_id))[0]


async def _list(
    conn: AsyncConnection, *, announcement_id: UUID | None = None, limit: int = 50
) -> list[AnnouncementResponse]:
    def count_of(status: str):
        return func.count(AnnouncementDelivery.id).filter(AnnouncementDelivery.status == status)

    counts = (
        select(
            AnnouncementDelivery.announcement_id,
            count_of("sent").label("sent_count"),
            count_of("pending").label("pending_count"),
            count_of("failed").label("failed_count"),
            count_of("cancelled").label("cancelled_count"),
        )
        .group_by(AnnouncementDelivery.announcement_id)
        .subquery()
    )
    query = (
        select(
            Announcement,
            Department.name.label("department_name"),
            User.first_name,
            User.last_name,
            User.telegram_username,
            User.telegram_id,
            func.coalesce(counts.c.sent_count, 0).label("sent_count"),
            func.coalesce(counts.c.pending_count, 0).label("pending_count"),
            func.coalesce(counts.c.failed_count, 0).label("failed_count"),
            func.coalesce(counts.c.cancelled_count, 0).label("cancelled_count"),
        )
        .outerjoin(Department, Announcement.department_id == Department.id)
        .outerjoin(User, Announcement.target_user_id == User.id)
        .outerjoin(counts, counts.c.announcement_id == Announcement.id)
        # Only this backend's bot: local and production share the database.
        .where(Announcement.bot_id.is_not_distinct_from(settings.telegram_bot_id))
        .order_by(Announcement.created_at.desc())
        .limit(limit)
    )
    if announcement_id:
        query = query.where(Announcement.id == announcement_id)

    rows = (await conn.execute(query)).mappings().all()
    return [
        AnnouncementResponse(
            id=row["id"],
            text=row["text"],
            audience=row["audience"],
            department_id=row["department_id"],
            department_name=row["department_name"],
            target_user_id=row["target_user_id"],
            target_user_label=(
                display_name(row, fallback=str(row["telegram_id"])) if row["target_user_id"] else None
            ),
            created_by=row["created_by"],
            created_at=row["created_at"],
            recipient_count=row["recipient_count"],
            sent_count=row["sent_count"],
            pending_count=row["pending_count"],
            failed_count=row["failed_count"],
            cancelled_count=row["cancelled_count"],
        )
        for row in rows
    ]
