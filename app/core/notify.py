"""
notify.py — Sends Telegram bot messages directly from the FastAPI backend.

This is used so the admin dashboard can notify users in real time when their
account status changes (PRO granted/revoked, banned, access reset, etc.)
without needing to route through the bot process.
"""
from __future__ import annotations

import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram_message(telegram_id: int, text: str) -> bool:
    """
    Sends a Telegram message to a user via the Bot HTTP API.
    Returns True on success, False on failure (never raises).
    """
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping user notification")
        return False

    url = TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    f"Telegram notify failed for telegram_id={telegram_id}: "
                    f"{resp.status_code} {resp.text}"
                )
                return False
        return True
    except Exception as exc:
        logger.warning(f"Telegram notify exception for telegram_id={telegram_id}: {exc}")
        return False
