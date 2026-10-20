from __future__ import annotations

from sqlalchemy import and_, false, or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.models.user import User
from app.schemas.announcement import AnnouncementAudience

# Same rule as UserAccess.has_dual_access: approved dual fee on top of PRO, or admin full access.
HAS_DUAL_ACCESS = and_(
    User.secondary_department_id.isnot(None),
    or_(User.is_full_access.is_(True), and_(User.is_pro.is_(True), User.secondary_department_unlocked.is_(True))),
)


def audience_filter(target: AnnouncementAudience) -> ColumnElement[bool]:
    """
    WHERE clause on users for an announcement audience. Banned users never get announcements.
    A department audience includes students of that main department and dual students who
    have it unlocked as their second department.
    """
    not_banned = User.is_banned.isnot(True)
    if target.audience == "all":
        match = true()
    elif target.audience == "pro":
        match = User.is_pro.is_(True)
    elif target.audience == "free":
        match = User.is_pro.is_(False)
    elif target.audience == "dual":
        match = HAS_DUAL_ACCESS
    elif target.audience == "department":
        match = or_(
            User.department_id == target.department_id,
            and_(User.secondary_department_id == target.department_id, HAS_DUAL_ACCESS),
        )
    elif target.audience == "users":
        match = User.id.in_(set(target.user_ids or []))
    else:
        match = false()
    return and_(not_banned, match)
