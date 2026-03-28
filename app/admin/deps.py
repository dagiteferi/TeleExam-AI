from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select

from app.core.config import settings
from app.db.postgres import db_conn
from app.models.admin_user import AdminUser
from app.schemas.admin import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")

async def get_admin_db():
    async with db_conn(telegram_id=None) as conn:
        yield conn

async def get_admin_user(
    token: str = Depends(oauth2_scheme),
    conn: AsyncConnection = Depends(get_admin_db),
) -> AdminUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "invalid_credentials", "message": "Could not validate credentials"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.admin_jwt_secret, algorithms=[settings.admin_jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except (JWTError, ValidationError):
        raise credentials_exception
    
    result = await conn.execute(select(AdminUser).where(AdminUser.email == token_data.email))
    admin_user = result.one_or_none()
    if admin_user is None:
        raise credentials_exception
    return admin_user

async def require_admin(current_user: AdminUser = Depends(get_admin_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "not_admin", "message": "Operation forbidden: requires admin role"}},
        )
    return current_user
