from __future__ import annotations

import asyncio
import hmac
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update, insert
import secrets
import datetime

from app.api.deps import get_redis
from app.core.config import settings
from app.core.security import create_access_token, hash_password, is_password_hashed, verify_password
from app.db.postgres import db_conn
from app.models.admin_user import AdminUser
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import Form
from app.schemas.admin import Token, InviteAdminRequest, InviteAdminResponse, AdminUserResponse, AdminPermission
from app.admin.deps import require_superadmin, get_admin_db

router = APIRouter(prefix="/auth")

# Wrong-password lockout: after MAX_FAILED attempts from one IP for one email,
# that email is blocked from that IP for LOCKOUT_SECONDS.
LOGIN_MAX_FAILED = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _login_fail_key(email: str, ip: str) -> str:
    return f"teleexam:admin_login_fail:{email}:{ip}"


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "invalid_credentials", "message": "Incorrect email or password"}},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _record_failed_login(redis: Redis, key: str) -> None:
    failed = await redis.incr(key)
    if failed == 1:
        await redis.expire(key, LOGIN_LOCKOUT_SECONDS)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    conn: AsyncConnection = Depends(get_admin_db),
    redis: Redis = Depends(get_redis),
) -> Token:
    """
    Login for both superadmin (.env) and regular admins (DB).
    Passwords are checked in constant time; DB admins' passwords are stored hashed.
    """
    email = form_data.username.strip().lower()
    password = form_data.password

    fail_key = _login_fail_key(email, request.client.host if request.client else "unknown")
    if int(await redis.get(fail_key) or 0) >= LOGIN_MAX_FAILED:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "too_many_attempts", "message": "Too many failed login attempts. Try again in 15 minutes."}},
        )

    if email == settings.superadmin_email.lower():
        if not hmac.compare_digest(password.encode(), settings.superadmin_password.encode()):
            await _record_failed_login(redis, fail_key)
            raise _invalid_credentials()
        await redis.delete(fail_key)
        token = create_access_token(
            data={"email": settings.superadmin_email, "role": "superadmin"},
            expires_delta=timedelta(minutes=settings.admin_jwt_ttl_minutes),
        )
        return Token(access_token=token, token_type="bearer")

    
    result = await conn.execute(select(AdminUser).where(AdminUser.email == email))
    admin = result.mappings().one_or_none()

    if not admin or not admin["is_active"]:
        await _record_failed_login(redis, fail_key)
        raise _invalid_credentials()

    # scrypt is CPU-heavy: run it off the event loop
    if not await asyncio.to_thread(verify_password, password, admin["password_hash"]):
        await _record_failed_login(redis, fail_key)
        raise _invalid_credentials()
    await redis.delete(fail_key)

    login_values = {"last_login_at": datetime.datetime.now(datetime.timezone.utc)}
    if not is_password_hashed(admin["password_hash"]):
        # Upgrade a legacy plain-text password to a hash on first successful login
        login_values["password_hash"] = await asyncio.to_thread(hash_password, password)
    await conn.execute(
        update(AdminUser)
        .where(AdminUser.email == email)
        .values(**login_values)
    )
    await conn.commit()

    token = create_access_token(
        data={"email": admin["email"], "role": admin["role"]},
        expires_delta=timedelta(minutes=settings.admin_jwt_ttl_minutes),
    )
    return Token(access_token=token, token_type="bearer")


@router.post("/invite", response_model=InviteAdminResponse)
async def invite_admin(
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    permissions: Annotated[list[AdminPermission], Form(...)],
    superadmin: dict = Depends(require_superadmin),
    conn: AsyncConnection = Depends(get_admin_db),
) -> InviteAdminResponse:
    """
    Superadmin-only: invite a new admin.
    Provides a native form in Swagger UI allowing the superadmin to type
    the email, specify the password manually, and select permissions from a dropdown.
    """
    email = email.strip().lower()

  
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

    
    await conn.execute(
        insert(AdminUser).values(
            email=email,
            password_hash=await asyncio.to_thread(hash_password, password),
            role="admin",
            permissions=[p.value for p in permissions],
            invited_by_email=settings.superadmin_email,
            is_active=True,
        )
    )
    await conn.commit()

    return InviteAdminResponse(
        email=email,
        password=password,  
        permissions=permissions,
        message="Admin successfully invited with your provided credentials.",
    )


@router.patch("/admins/{email}/permissions")
async def update_admin_permissions(
    email: str,
    permissions: list[AdminPermission],
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

    stringified_permissions = [p.value for p in permissions]

    result = await conn.execute(update(AdminUser).where(AdminUser.email == email).values(permissions=stringified_permissions))
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
    admins = result.mappings().all()
    return [AdminUserResponse(**a) for a in admins]