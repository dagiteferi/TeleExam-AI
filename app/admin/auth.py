from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update
import secrets
import datetime

from app.core.config import settings
from app.core.security import create_access_token
from app.db.postgres import db_conn
from app.models.admin_user import AdminUser
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from app.schemas.admin import Token, InviteAdminRequest, InviteAdminResponse, AdminUserResponse
from app.admin.deps import require_superadmin, get_admin_db

router = APIRouter(prefix="/auth")

@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    conn: AsyncConnection = Depends(get_admin_db),
) -> Token:
    """
    Login for both superadmin (.env) and regular admins (DB).
    Uses plain string comparison for superadmin; DB lookup for invited admins.
    """
    email = form_data.username.strip().lower()
    password = form_data.password

    
    if email == settings.superadmin_email.lower():
        if password != settings.superadmin_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "invalid_credentials", "message": "Incorrect email or password"}},
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token(
            data={"email": settings.superadmin_email, "role": "superadmin"},
            expires_delta=timedelta(minutes=settings.admin_jwt_ttl_minutes),
        )
        return Token(access_token=token, token_type="bearer")

    
    result = await conn.execute(select(AdminUser).where(AdminUser.email == email))
    admin = result.scalars().one_or_none()

    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_credentials", "message": "Incorrect email or password"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

   
    if password != admin.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_credentials", "message": "Incorrect email or password"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

  
    await conn.execute(
        update(AdminUser)
        .where(AdminUser.email == email)
        .values(last_login_at=datetime.datetime.now(datetime.timezone.utc))
    )
    await conn.commit()

    token = create_access_token(
        data={"email": admin.email, "role": admin.role},
        expires_delta=timedelta(minutes=settings.admin_jwt_ttl_minutes),
    )
    return Token(access_token=token, token_type="bearer")


@router.post("/invite", response_model=InviteAdminResponse)
async def invite_admin(
    request: InviteAdminRequest,
    superadmin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> InviteAdminResponse:
    """
    Superadmin-only: invite a new admin with a specific email and permissions.
    A random secure password is auto-generated and returned ONCE.
    The invited admin cannot change their own credentials.
    """
    email = request.email.strip().lower()

  
    existing = await conn.scalar(select(AdminUser.id).where(AdminUser.email == email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "admin_exists", "message": "An admin with this email already exists"}},
        )

   
    if email == settings.superadmin_email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "reserved_email", "message": "This email is reserved for the superadmin"}},
        )

    
    raw_password = secrets.token_urlsafe(12)

    new_admin = AdminUser(
        email=email,
        password_hash=raw_password,  
        role="admin",
        permissions=request.permissions,
        invited_by_email=settings.superadmin_email,
        is_active=True,
    )
    conn.add(new_admin)
    await conn.commit()

    return InviteAdminResponse(
        email=email,
        password=raw_password,  
        permissions=request.permissions,
        message="Admin invited. Share these credentials securely. They cannot be changed by the admin.",
    )


@router.patch("/admins/{email}/permissions")
async def update_admin_permissions(
    email: str,
    permissions: list[str],
    superadmin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> dict:
    """Superadmin-only: update the permissions of an invited admin."""
    email = email.strip().lower()

    if email == settings.superadmin_email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "cannot_modify_superadmin", "message": "Cannot modify superadmin"}},
        )

    result = await conn.execute(update(AdminUser).where(AdminUser.email == email).values(permissions=permissions))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Admin not found"}})
    await conn.commit()
    return {"success": True, "email": email, "permissions": permissions}


@router.patch("/admins/{email}/deactivate")
async def deactivate_admin(
    email: str,
    superadmin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> dict:
    """Superadmin-only: deactivate (disable) an invited admin."""
    email = email.strip().lower()
    if email == settings.superadmin_email.lower():
        raise HTTPException(status_code=400, detail={"error": {"code": "cannot_deactivate_superadmin"}})

    await conn.execute(update(AdminUser).where(AdminUser.email == email).values(is_active=False))
    await conn.commit()
    return {"success": True, "message": f"Admin {email} has been deactivated."}


@router.get("/admins", response_model=list[AdminUserResponse])
async def list_admins(
    superadmin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[AdminUserResponse]:
    """Superadmin-only: list all invited admins."""
    result = await conn.execute(select(AdminUser))
    admins = result.scalars().all()
    return [AdminUserResponse.model_validate(a, from_attributes=True) for a in admins]