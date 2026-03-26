from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.models.user import UserUpsertRequest, UserUpsertResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@router.post("/upsert", response_model=UserUpsertResponse)
async def upsert_user(
    _: UserUpsertRequest,
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserUpsertResponse:
    user = await UserService().upsert_user(conn, telegram_id=telegram_id)
    return UserUpsertResponse(success=True, **user)

