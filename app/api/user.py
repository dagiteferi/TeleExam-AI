from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select

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
    
    # Build response with department info if available
    response_data = {
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "invite_code": user.invite_code,
        "invite_count": user.invite_count,
        "is_pro": user.is_pro,
        "plan_expiry": user.plan_expiry,
        "department_id": user.department_id,
    }
    
    if user.department_id:
        from app.models.department import Department
        dept_stmt = select(Department.name).where(Department.id == user.department_id)
        dept_result = await conn.execute(dept_stmt)
        dept_name = dept_result.scalar_one_or_none()
        response_data["department_name"] = dept_name
    
    return UserResponse(**response_data)


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> UserResponse:
    user = await UserService().get_user_by_telegram_id(conn, telegram_id=telegram_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
        
    response_data = {
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "invite_code": user.invite_code,
        "invite_count": user.invite_count,
        "is_pro": user.is_pro,
        "plan_expiry": user.plan_expiry,
        "department_id": user.department_id,
    }
    
    if user.department_id:
        from app.models.department import Department
        dept_stmt = select(Department.name).where(Department.id == user.department_id)
        dept_result = await conn.execute(dept_stmt)
        dept_name = dept_result.scalar_one_or_none()
        response_data["department_name"] = dept_name
        
    return UserResponse(**response_data)




@router.get("/invited")
async def get_invited_users(
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> list[dict]:
    """
    Returns list of users invited by the current user.
    """
    from sqlalchemy import select
    from app.models.user import User
    
    result = await conn.execute(
        select(User.id, User.first_name, User.created_at, User.telegram_id)
        .where(User.invited_by_user_id == telegram_id)
        .order_by(User.created_at.desc())
    )
    
    return [
        {
            "id": str(row.id),
            "first_name": row.first_name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "telegram_id": row.telegram_id
        }
        for row in result.fetchall()
    ]
