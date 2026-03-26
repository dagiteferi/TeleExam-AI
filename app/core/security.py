from __future__ import annotations
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.config import settings


def validate_telegram_secret(secret: str | None) -> bool:
    if not secret:
        return False
    return secret == settings.telegram_webhook_secret


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.admin_jwt_ttl_minutes)
    to_encode.update({"exp": expire, "sub": data["email"]})
    encoded_jwt = jwt.encode(to_encode, settings.admin_jwt_secret, algorithm=settings.admin_jwt_algorithm)
    return encoded_jwt


