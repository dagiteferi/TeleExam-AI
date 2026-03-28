from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update

from app.admin.deps import require_admin
from app.db.postgres import db_conn
from app.db.redis import get_redis_client, get_flag_key
from app.models.admin_user import AdminUser
from app.models.user import User
from app.schemas.admin import AdminUserResponse, UserAdminUpdate, UserFlaggedResponse
from redis.asyncio import Redis

router = APIRouter(prefix="/users", dependencies=[Depends(require_admin)])

@router.get("/", response_model=list[AdminUserResponse])
async def get_all_users(
    conn: AsyncConnection = Depends(db_conn),
    limit: int = 100,
    offset: int = 0,
) -> list[AdminUserResponse]:
    result = await conn.execute(select(User).limit(limit).offset(offset))
    users = result.scalars().all()
    return [AdminUserResponse.model_validate(user) for user in users]

@router.patch("/{user_id}", response_model=AdminUserResponse)
async def update_user_by_admin(
    user_id: UUID,
    user_update: UserAdminUpdate,
    conn: AsyncConnection = Depends(db_conn),
) -> AdminUserResponse:
    stmt = update(User).where(User.id == user_id).values(**user_update.model_dump(exclude_unset=True))
    await conn.execute(stmt)
    await conn.commit()
    
    updated_user = await conn.scalar(select(User).where(User.id == user_id))
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})
    return AdminUserResponse.model_validate(updated_user)

@router.post("/{user_id}/ban", response_model=AdminUserResponse)
async def ban_user(
    user_id: UUID,
    reason: str,
    duration_hours: int | None = None,
    conn: AsyncConnection = Depends(db_conn),
    redis: Redis = Depends(get_redis_client),
) -> AdminUserResponse:
    stmt = update(User).where(User.id == user_id).values(is_banned=True, ban_reason=reason)
    await conn.execute(stmt)
    await conn.commit()

    user = await conn.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})

    flag_key = get_flag_key(user.telegram_id)
    ttl = duration_hours * 3600 if duration_hours else 24 * 3600
    await redis.set(flag_key, "blocked", ex=ttl)

    return AdminUserResponse.model_validate(user)

@router.post("/{user_id}/unban", response_model=AdminUserResponse)
async def unban_user(
    user_id: UUID,
    conn: AsyncConnection = Depends(db_conn),
    redis: Redis = Depends(get_redis_client),
) -> AdminUserResponse:
    stmt = update(User).where(User.id == user_id).values(is_banned=False, ban_reason=None)
    await conn.execute(stmt)
    await conn.commit()

    user = await conn.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "user_not_found", "message": "User not found"}})

    flag_key = get_flag_key(user.telegram_id)
    await redis.delete(flag_key)

    return AdminUserResponse.model_validate(user)

@router.get("/flagged", response_model=list[UserFlaggedResponse])
async def get_flagged_users(
    conn: AsyncConnection = Depends(db_conn),
    redis: Redis = Depends(get_redis_client),
) -> list[UserFlaggedResponse]:
    pg_banned_users = await conn.execute(select(User).where(User.is_banned == True))
    pg_banned_users = pg_banned_users.scalars().all()

    redis_flagged_keys = []
    async for key in redis.scan_iter(f"{get_flag_key('*')}*"):
        redis_flagged_keys.append(key)
    
    redis_flagged_telegram_ids = []
    for key in redis_flagged_keys:
        try:
            telegram_id_str = key.split(':')[-1]
            redis_flagged_telegram_ids.append(int(telegram_id_str))
        except (ValueError, IndexError):
            continue

    flagged_users_data = {}

    for user in pg_banned_users:
        flagged_users_data[user.telegram_id] = UserFlaggedResponse(
            user_id=user.id,
            telegram_id=user.telegram_id,
            is_banned_pg=True,
            ban_reason_pg=user.ban_reason,
            flag_redis=None,
        )
    
    if redis_flagged_telegram_ids:
        redis_users = await conn.execute(select(User).where(User.telegram_id.in_(redis_flagged_telegram_ids)))
        redis_users = redis_users.scalars().all()
        
        for user in redis_users:
            flag_key = get_flag_key(user.telegram_id)
            flag_value = await redis.get(flag_key)
            if user.telegram_id in flagged_users_data:
                flagged_users_data[user.telegram_id].flag_redis = flag_value
            else:
                flagged_users_data[user.telegram_id] = UserFlaggedResponse(
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    is_banned_pg=user.is_banned,
                    ban_reason_pg=user.ban_reason,
                    flag_redis=flag_value,
                )
    
    return list(flagged_users_data.values())
