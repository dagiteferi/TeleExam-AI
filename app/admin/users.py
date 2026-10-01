from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update, or_

from app.admin.deps import require_admin, require_superadmin, require_permission, get_admin_db
from app.db.postgres import db_conn
from app.db.redis import get_redis_client, get_flag_key
from app.models.user import User
from app.schemas.admin import (
    PlatformUserResponse,
    UserAdminUpdate,
    UserFlaggedResponse,
    GrantFullAccessRequest,
    GrantFullAccessResponse,
)
from app.core.notify import send_telegram_message
from redis.asyncio import Redis

router = APIRouter(prefix="/users")


# ─────────────────────────────────────────────
#  STATIC routes MUST come before /{user_id}/*
# ─────────────────────────────────────────────

@router.get("/", response_model=list[PlatformUserResponse], dependencies=[Depends(require_permission("view_users"))])
async def get_all_users(
    conn: AsyncConnection = Depends(get_admin_db),
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
    is_pro: bool | None = None,
    is_banned: bool | None = None,
    invited_by: UUID | None = None,
) -> list[PlatformUserResponse]:
    """Requires: view_users permission or superadmin."""
    query = select(User)

    if search:
        try:
            tid = int(search)
            query = query.where(User.telegram_id == tid)
        except ValueError:
            search_query = f"%{search}%"
            query = query.where(
                or_(
                    User.telegram_username.ilike(search_query),
                    User.first_name.ilike(search_query),
                    User.last_name.ilike(search_query),
                )
            )

    if is_pro is not None:
        query = query.where(User.is_pro == is_pro)

    if is_banned is not None:
        query = query.where(User.is_banned == is_banned)

    if invited_by:
        query = query.where(User.invited_by_user_id == invited_by)

    query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await conn.execute(query)
    users = result.mappings().all()
    return [PlatformUserResponse(**user) for user in users]


@router.get("/flagged", response_model=list[UserFlaggedResponse], dependencies=[Depends(require_permission("view_users"))])
async def get_flagged_users(
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> list[UserFlaggedResponse]:
    """Requires: view_users permission or superadmin."""
    pg_banned_users_result = await conn.execute(select(User).where(User.is_banned == True))
    pg_banned_users = pg_banned_users_result.mappings().all()

    redis_flagged_keys = []
    async for key in redis.scan_iter(f"{get_flag_key('*')}*"):
        redis_flagged_keys.append(key)

    redis_flagged_telegram_ids = []
    for key in redis_flagged_keys:
        try:
            redis_flagged_telegram_ids.append(int(key.split(':')[-1]))
        except (ValueError, IndexError):
            continue

    flagged_users_data = {}

    for user in pg_banned_users:
        flagged_users_data[user["telegram_id"]] = UserFlaggedResponse(
            user_id=user["id"], telegram_id=user["telegram_id"],
            is_banned_pg=True, ban_reason_pg=user["ban_reason"], flag_redis=None,
        )

    if redis_flagged_telegram_ids:
        redis_users_result = await conn.execute(select(User).where(User.telegram_id.in_(redis_flagged_telegram_ids)))
        redis_users = redis_users_result.mappings().all()

        for user in redis_users:
            flag_key = get_flag_key(user["telegram_id"])
            flag_value = await redis.get(flag_key)
            if user["telegram_id"] in flagged_users_data:
                flagged_users_data[user["telegram_id"]].flag_redis = flag_value
            else:
                flagged_users_data[user["telegram_id"]] = UserFlaggedResponse(
                    user_id=user["id"], telegram_id=user["telegram_id"],
                    is_banned_pg=user["is_banned"], ban_reason_pg=user["ban_reason"], flag_redis=flag_value,
                )

    return list(flagged_users_data.values())


@router.post(
    "/grant-full-access",
    response_model=GrantFullAccessResponse,
    dependencies=[Depends(require_superadmin)],
    summary="Grant a user unlimited access (bypasses all invite locks)",
)
async def grant_full_access(
    body: GrantFullAccessRequest,
    conn: AsyncConnection = Depends(get_admin_db),
) -> GrantFullAccessResponse:
    """
    Superadmin only.
    Sets `is_full_access = True` for the user with the given `telegram_id`.
    """
    result = await conn.execute(select(User).where(User.telegram_id == body.telegram_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": f"No user found with telegram_id={body.telegram_id}"}},
        )

    await conn.execute(
        update(User)
        .where(User.telegram_id == body.telegram_id)
        .values(is_full_access=True)
    )
    await conn.commit()

    await send_telegram_message(
        body.telegram_id,
        "🔓 <b>Full Access Granted!</b>\n\n"
        "You have been granted <b>unlimited access</b> to all courses and exam years by an administrator.\n"
        "You can now use all content without any invite restrictions."
    )

    return GrantFullAccessResponse(
        telegram_id=body.telegram_id,
        is_full_access=True,
        message=f"✅ Full access granted to telegram_id={body.telegram_id}. They can now use all content without invites.",
    )


@router.post(
    "/revoke-full-access",
    response_model=GrantFullAccessResponse,
    dependencies=[Depends(require_superadmin)],
    summary="Revoke unlimited access — user returns to normal invite-based locking",
)
async def revoke_full_access(
    body: GrantFullAccessRequest,
    conn: AsyncConnection = Depends(get_admin_db),
) -> GrantFullAccessResponse:
    """
    Superadmin only.
    Sets `is_full_access = False` for the user with the given `telegram_id`.
    """
    result = await conn.execute(select(User).where(User.telegram_id == body.telegram_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": f"No user found with telegram_id={body.telegram_id}"}},
        )

    await conn.execute(
        update(User)
        .where(User.telegram_id == body.telegram_id)
        .values(is_full_access=False)
    )
    await conn.commit()

    await send_telegram_message(
        body.telegram_id,
        "🔒 <b>Full Access Revoked</b>\n\n"
        "Your unlimited access has been revoked by an administrator.\n"
        "You are now subject to the normal invite-based content locking system."
    )

    return GrantFullAccessResponse(
        telegram_id=body.telegram_id,
        is_full_access=False,
        message=f"🔒 Full access revoked from telegram_id={body.telegram_id}. Normal invite locks restored.",
    )


# ─────────────────────────────────────────────
#  PARAMETERIZED routes  /{user_id}/*
# ─────────────────────────────────────────────

@router.patch("/{user_id}", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("view_users"))])
async def update_user_by_admin(
    user_id: UUID,
    user_update: UserAdminUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PlatformUserResponse:
    """Requires: view_users permission or superadmin."""
    stmt = update(User).where(User.id == user_id).values(**user_update.model_dump(exclude_unset=True))
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(User).where(User.id == user_id))
    updated_user = result.mappings().one_or_none()
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})
    return PlatformUserResponse(**updated_user)


@router.post("/{user_id}/toggle-pro", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("view_users"))])
async def toggle_user_pro(
    user_id: UUID,
    is_pro: bool | None = None,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PlatformUserResponse:
    """
    Toggles or explicitly sets the PRO status of a user.
    - No query param → toggle current value
    - ?is_pro=true  → force PRO
    - ?is_pro=false → force Free (revoke PRO)
    Sends a Telegram notification to the user after changing their status.
    """
    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found"}},
        )

    new_pro_status = not user["is_pro"] if is_pro is None else is_pro

    await conn.execute(update(User).where(User.id == user_id).values(is_pro=new_pro_status))
    await conn.commit()

    # Send Telegram notification
    name = user.get("first_name") or user.get("telegram_username") or "there"
    if new_pro_status:
        await send_telegram_message(
            user["telegram_id"],
            f"⭐ <b>You're now PRO, {name}!</b>\n\n"
            "An administrator has upgraded your account to <b>PRO</b>.\n\n"
            "You now have access to:\n"
            "• 🤖 <b>AI Tutor</b> — unlimited explanations & study plans\n"
            "• 📚 <b>All Courses & Exam Years</b> — full content unlocked\n"
            "• 🎯 <b>Unlimited Daily Questions</b>\n\n"
            "Enjoy your PRO experience! 🎉"
        )
    else:
        await send_telegram_message(
            user["telegram_id"],
            f"🔓 <b>PRO Access Revoked, {name}</b>\n\n"
            "Your <b>PRO</b> subscription has been revoked by an administrator.\n"
            "Your account has been returned to the <b>Free</b> tier.\n\n"
            "You can still access free content and earn invites to unlock more.\n"
            "Contact support if you believe this was a mistake."
        )

    updated_result = await conn.execute(select(User).where(User.id == user_id))
    updated_user = updated_result.mappings().one_or_none()
    return PlatformUserResponse(**updated_user)


@router.post("/{user_id}/reset-access", response_model=PlatformUserResponse, dependencies=[Depends(require_superadmin)])
async def reset_user_access(
    user_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PlatformUserResponse:
    """
    Superadmin only.
    Fully resets a user's access: is_pro=False, is_full_access=False, invite_count=0.
    Notifies the user via Telegram.
    """
    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found"}},
        )

    await conn.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_pro=False, is_full_access=False, invite_count=0)
    )
    await conn.commit()

    name = user.get("first_name") or user.get("telegram_username") or "there"
    await send_telegram_message(
        user["telegram_id"],
        f"⚠️ <b>Account Access Reset, {name}</b>\n\n"
        "Your account access has been fully reset by an administrator:\n"
        "• PRO status: <b>Removed</b>\n"
        "• Full access: <b>Removed</b>\n"
        "• Invite count: <b>Reset to 0</b>\n\n"
        "You are now on the Free tier. Contact support if you have questions."
    )

    updated_result = await conn.execute(select(User).where(User.id == user_id))
    updated_user = updated_result.mappings().one_or_none()
    return PlatformUserResponse(**updated_user)


@router.post("/{user_id}/ban", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("ban_user"))])
async def ban_user(
    user_id: UUID,
    reason: str,
    duration_hours: int | None = None,
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> PlatformUserResponse:
    """Requires: ban_user permission or superadmin."""
    stmt = update(User).where(User.id == user_id).values(is_banned=True, ban_reason=reason)
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})

    flag_key = get_flag_key(user["telegram_id"])
    ttl = duration_hours * 3600 if duration_hours else 24 * 3600
    await redis.set(flag_key, "blocked", ex=ttl)

    name = user.get("first_name") or user.get("telegram_username") or "there"
    duration_msg = f" for {duration_hours} hour(s)" if duration_hours else ""
    await send_telegram_message(
        user["telegram_id"],
        f"🚫 <b>Account Restricted, {name}</b>\n\n"
        f"Your account has been <b>banned{duration_msg}</b> by an administrator.\n"
        f"Reason: <i>{reason}</i>\n\n"
        "Contact support if you believe this was a mistake."
    )

    return PlatformUserResponse(**user)


@router.post("/{user_id}/unban", response_model=PlatformUserResponse, dependencies=[Depends(require_permission("ban_user"))])
async def unban_user(
    user_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis_client),
) -> PlatformUserResponse:
    """Requires: ban_user permission or superadmin."""
    stmt = update(User).where(User.id == user_id).values(is_banned=False, ban_reason=None)
    await conn.execute(stmt)
    await conn.commit()

    result = await conn.execute(select(User).where(User.id == user_id))
    user = result.mappings().one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})

    flag_key = get_flag_key(user["telegram_id"])
    await redis.delete(flag_key)

    name = user.get("first_name") or user.get("telegram_username") or "there"
    await send_telegram_message(
        user["telegram_id"],
        f"✅ <b>Account Restored, {name}!</b>\n\n"
        "Your account restriction has been lifted by an administrator.\n"
        "You can now use TeleExam again. Welcome back!"
    )

    return PlatformUserResponse(**user)
