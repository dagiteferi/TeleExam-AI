from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.user import User


@dataclass
class UserAccess:
    invite_count: int = 0
    is_pro: bool = False
    is_full_access: bool = False
    department_id: uuid.UUID | None = None
    secondary_department_id: uuid.UUID | None = None
    secondary_department_unlocked: bool = False
    active_department_id: uuid.UUID | None = None

    @property
    def has_dual_access(self) -> bool:
        """Second department usable: dual fee approved on top of PRO, or admin full access."""
        if self.secondary_department_id is None:
            return False
        return self.is_full_access or (self.is_pro and self.secondary_department_unlocked)

    @property
    def effective_department_id(self) -> uuid.UUID | None:
        """The department being studied now; falls back to the main one if the second is not usable."""
        if (
            self.active_department_id is not None
            and self.active_department_id == self.secondary_department_id
            and self.has_dual_access
        ):
            return self.active_department_id
        return self.department_id

    def can_use_department(self, department_id: uuid.UUID | None) -> bool:
        if department_id is None:
            return True
        if self.department_id is not None and department_id == self.department_id:
            return True
        return department_id == self.secondary_department_id and self.has_dual_access

    def fully_unlocks(self, department_id: uuid.UUID | None) -> bool:
        """True when invite/year locks should not apply for this department."""
        if not self.can_use_department(department_id):
            return False
        if self.is_full_access:
            return True
        if department_id is not None and self.department_id is not None and department_id == self.department_id:
            return self.is_pro
        return department_id is not None and department_id == self.secondary_department_id and self.has_dual_access


_ACCESS_COLUMNS = (
    User.invite_count,
    User.is_pro,
    User.is_full_access,
    User.department_id,
    User.secondary_department_id,
    User.secondary_department_unlocked,
    User.active_department_id,
)


class AccessService:
    @staticmethod
    async def get_by_telegram_id(conn: AsyncConnection, telegram_id: int | None) -> UserAccess | None:
        if not telegram_id:
            return None
        result = await conn.execute(select(*_ACCESS_COLUMNS).where(User.telegram_id == telegram_id))
        return AccessService.from_row(result.fetchone())

    @staticmethod
    async def get_by_user_id(conn: AsyncConnection, user_id: uuid.UUID | None) -> UserAccess | None:
        if not user_id:
            return None
        result = await conn.execute(select(*_ACCESS_COLUMNS).where(User.id == user_id))
        return AccessService.from_row(result.fetchone())

    @staticmethod
    def from_row(row) -> UserAccess | None:
        if not row:
            return None
        return UserAccess(
            invite_count=row.invite_count or 0,
            is_pro=bool(row.is_pro),
            is_full_access=bool(row.is_full_access),
            department_id=row.department_id,
            secondary_department_id=row.secondary_department_id,
            secondary_department_unlocked=bool(row.secondary_department_unlocked),
            active_department_id=row.active_department_id,
        )
