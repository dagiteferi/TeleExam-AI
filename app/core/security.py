from __future__ import annotations
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.config import settings

# scrypt parameters (stdlib, no extra dependency): ~16 MB memory and a few tens of ms per hash
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _SCRYPT_DKLEN = 2**14, 8, 1, 32
_HASH_PREFIX = "scrypt$"


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=_SCRYPT_DKLEN)


def hash_password(password: str) -> str:
    """Returns 'scrypt$n$r$p$salt$hash' (base64 parts) for storing in admin_users.password_hash."""
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    b64 = lambda b: base64.b64encode(b).decode()
    return f"{_HASH_PREFIX}{_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(digest)}"


def is_password_hashed(stored: str) -> bool:
    return stored.startswith(_HASH_PREFIX)


def verify_password(password: str, stored: str) -> bool:
    """
    Constant-time check of a password against a stored hash.
    Rows still holding a plain-text password (from before hashing was added) are
    compared directly so admins can still log in; the login then re-hashes them.
    """
    if not is_password_hashed(stored):
        return hmac.compare_digest(password.encode(), stored.encode())
    try:
        _, n, r, p, salt_b64, digest_b64 = stored.split("$")
        digest = _scrypt(password, base64.b64decode(salt_b64), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


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


