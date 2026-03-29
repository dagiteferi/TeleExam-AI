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




async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    conn: AsyncConnection = Depends(get_admin_db),
) -> dict:
    """
    Decodes JWT and returns a dict of admin info.
    Superadmin is verified against .env (no DB lookup needed).
    Regular admins are verified against DB.
    Returns: {"email": str, "role": str, "permissions": list[str], "is_superadmin": bool}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "invalid_credentials", "message": "Could not validate credentials"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.admin_jwt_secret, algorithms=[settings.admin_jwt_algorithm])
        email: str = payload.get("sub")
        role: str = payload.get("role", "admin")
        if not email:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception

   
    if email == settings.superadmin_email and role == "superadmin":
        return {
            "email": email,
            "role": "superadmin",
            "permissions": ["*"],  
            "is_superadmin": True,
        }

    
    result = await conn.execute(select(AdminUser).where(AdminUser.email == email))
    admin = result.mappings().one_or_none()
    if not admin or not admin["is_active"]:
        raise credentials_exception

    return {
        "email": admin["email"],
        "role": admin["role"],
        "permissions": admin["permissions"] or [],
        "is_superadmin": False,
    }




def require_permission(permission: str):
    """
    Returns a FastAPI dependency that checks if the current admin
    has a specific permission OR is superadmin.
    """
    async def _check(admin: dict = Depends(get_current_admin)):
        if admin["is_superadmin"] or "*" in admin["permissions"] or permission in admin["permissions"]:
            return admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": f"Requires permission: {permission}"}},
        )
    return _check


async def require_superadmin(admin: dict = Depends(get_current_admin)) -> dict:
    """Only superadmin can access this endpoint."""
    if not admin["is_superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "superadmin_required", "message": "Only superadmin can perform this action"}},
        )
    return admin


async def require_admin(admin: dict = Depends(get_current_admin)) -> dict:
    """Any active admin (including superadmin) can access."""
    return admin
