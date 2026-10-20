from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update

from app.api.deps import get_current_telegram_id, get_db_conn
from app.core.config import settings
from app.core.utils import display_name
from app.models.department import Department
from app.models.user import User
from app.schemas.users import ActiveDepartmentRequest, DualDepartmentRequest, UserResponse, UserUpsertRequest
from app.services.access_service import AccessService
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


async def _department_names(conn: AsyncConnection, *department_ids: UUID | None) -> dict[UUID, str]:
    ids = [dept_id for dept_id in department_ids if dept_id]
    if not ids:
        return {}
    result = await conn.execute(select(Department.id, Department.name).where(Department.id.in_(ids)))
    return {row.id: row.name for row in result}


async def build_user_response(conn: AsyncConnection, user) -> UserResponse:
    names = await _department_names(conn, user.department_id, getattr(user, "secondary_department_id", None))
    access = AccessService.from_row(user)
    active_id = access.effective_department_id
    return UserResponse(
        user_id=user.id,
        telegram_id=user.telegram_id,
        invite_code=user.invite_code,
        invite_count=user.invite_count,
        is_pro=user.is_pro,
        is_full_access=bool(getattr(user, "is_full_access", False)),
        plan_expiry=user.plan_expiry,
        department_id=user.department_id,
        department_name=names.get(user.department_id),
        secondary_department_id=getattr(user, "secondary_department_id", None),
        secondary_department_name=names.get(getattr(user, "secondary_department_id", None)),
        secondary_department_unlocked=bool(getattr(user, "secondary_department_unlocked", False)),
        has_dual_access=access.has_dual_access,
        active_department_id=active_id,
        active_department_name=names.get(active_id),
    )


@router.post("/upsert", response_model=UserResponse)
async def upsert_user(
    user_data: UserUpsertRequest,
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserResponse:
    user = await UserService().upsert_user(conn, telegram_id=telegram_id, user_data=user_data)
    return await build_user_response(conn, user)


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserResponse:
    user = await UserService().get_user_by_telegram_id(conn, telegram_id=telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await build_user_response(conn, user)


@router.post("/dual-department", response_model=UserResponse)
async def set_dual_department(
    body: DualDepartmentRequest,
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserResponse:
    """
    Choose a second department. Requires a paid (PRO) plan.
    The second department stays locked until the extra dual fee is approved,
    unless the user already has admin full access.
    """
    user = await UserService().get_user_by_telegram_id(conn, telegram_id=telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.department_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "primary_department_required", "message": "Choose your main department first."}},
        )
    if not user.is_pro and not getattr(user, "is_full_access", False):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "dual_requires_pro",
                    "message": (
                        f"Upgrade to PRO for {settings.PRO_PRICE_BIRR} Birr first, "
                        f"then pay {settings.DUAL_DEPT_PRICE_BIRR} Birr to unlock a second department."
                    ),
                }
            },
        )
    if body.department_id == user.department_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "same_department", "message": "Your dual department must be different from your main department."}},
        )
    if user.secondary_department_unlocked and user.secondary_department_id and body.department_id != user.secondary_department_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "dual_already_unlocked", "message": "Your second department is already unlocked and cannot be changed."}},
        )

    dept = await conn.execute(
        select(Department.id).where(Department.id == body.department_id, Department.is_active == True)
    )
    if not dept.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Department not found")

    now = datetime.datetime.utcnow()
    unlock_now = bool(getattr(user, "is_full_access", False))
    await conn.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            secondary_department_id=body.department_id,
            secondary_department_unlocked=unlock_now or user.secondary_department_unlocked,
            updated_at=now,
        )
    )
    await conn.commit()

    user = await UserService().get_user_by_telegram_id(conn, telegram_id=telegram_id)
    return await build_user_response(conn, user)


@router.post("/active-department", response_model=UserResponse)
async def set_active_department(
    body: ActiveDepartmentRequest,
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserResponse:
    """
    Switch the department being studied. Exams, practice, progress and the AI
    study plan all follow it. Switching to the second department requires
    dual access (PRO + approved dual fee, or admin full access).
    """
    user = await UserService().get_user_by_telegram_id(conn, telegram_id=telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access = AccessService.from_row(user)
    if body.department_id == user.department_id:
        new_active = None
    elif body.department_id == user.secondary_department_id and access.has_dual_access:
        new_active = body.department_id
    else:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "department_locked",
                    "message": "You can only switch to your second department after your dual degree payment is approved.",
                }
            },
        )

    await conn.execute(
        update(User)
        .where(User.id == user.id)
        .values(active_department_id=new_active, updated_at=datetime.datetime.utcnow())
    )
    await conn.commit()

    user = await UserService().get_user_by_telegram_id(conn, telegram_id=telegram_id)
    return await build_user_response(conn, user)


@router.get("/invited")
async def get_invited_users(
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> list[dict]:
    """
    Returns list of users invited by the current user.
    """
    my_user = await UserService().get_user_by_telegram_id(conn, telegram_id)
    if not my_user:
        return []

    result = await conn.execute(
        select(User.id, User.first_name, User.last_name, User.telegram_username, User.created_at, User.telegram_id)
        .where(User.invited_by_user_id == my_user.id)
        .order_by(User.created_at.desc())
    )

    return [
        {
            "id": str(row.id),
            "first_name": row.first_name,
            "last_name": row.last_name,
            "full_name": display_name(row, fallback="User"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "telegram_id": row.telegram_id,
        }
        for row in result.fetchall()
    ]
