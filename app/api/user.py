from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.schemas.users import UserUpsertRequest, UserResponse # Updated import
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@router.post("/upsert", response_model=UserResponse) # Updated response_model
async def upsert_user(
    user_data: UserUpsertRequest, # Added user_data parameter
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserResponse: # Updated return type
    user = await UserService().upsert_user(conn, telegram_id=telegram_id, user_data=user_data) # Pass user_data
    return UserResponse(
        user_id=user.id,
        telegram_id=user.telegram_id,
        invite_code=user.invite_code,
        invite_count=user.invite_count,
        is_pro=user.is_pro,
        plan_expiry=user.plan_expiry,
    )

