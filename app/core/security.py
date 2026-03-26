from __future__ import annotations
from app.core.config import settings


def validate_telegram_secret(secret: str | None) -> bool:
    if not secret:
        return False
    return secret == settings.telegram_webhook_secret

