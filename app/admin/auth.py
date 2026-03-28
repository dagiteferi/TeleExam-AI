from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token # Added this import
from app.db.postgres import db_conn
from app.models.admin_user import AdminUser
from app.schemas.admin import Token

router = APIRouter(prefix="/auth")

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    conn: AsyncConnection = Depends(db_conn),
) -> Token:
    admin_user = await conn.scalar(select(AdminUser).where(AdminUser.email == form_data.username))
    if not admin_user or not admin_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_credentials", "message": "Incorrect username or password"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if form_data.password != admin_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_credentials", "message": "Incorrect username or password"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.admin_jwt_ttl_minutes)
    access_token = create_access_token(
        data={"email": admin_user.email, "role": admin_user.role}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")