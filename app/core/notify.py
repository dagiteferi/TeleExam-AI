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


async def _send_via_bot_relay(telegram_id: int, text: str, refresh_menu: bool) -> bool:
    """Asks the bot service to send the message (for hosts that block api.telegram.org)."""
    try:
        # Generous timeout: a sleeping bot host (e.g. Render free tier) can take ~50s to wake up
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                settings.bot_notify_url,
                json={"telegram_id": telegram_id, "text": text, "refresh_menu": refresh_menu},
                headers={"X-Telegram-Secret": settings.telegram_webhook_secret},
            )
            if resp.status_code != 200:
                logger.warning(
                    f"Bot relay notify failed for telegram_id={telegram_id}: "
                    f"{resp.status_code} {resp.text}"
                )
                return False
        return True
    except Exception as exc:
        logger.warning(f"Bot relay notify exception for telegram_id={telegram_id}: {exc!r}")
        return False


async def wake_announcement_sender() -> None:
    """
    Tells the bot to start sending announcements now instead of at its next check.
    Uses the relay's host (BOT_NOTIFY_URL). Best effort: the bot checks regularly anyway.
    """
    if not settings.bot_notify_url:
        return
    url = settings.bot_notify_url.split("/internal/", 1)[0] + "/internal/announcements/wake"
    try:
        # Generous timeout: a sleeping bot host (e.g. Render free tier) can take ~50s to wake up
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.post(url, headers={"X-Telegram-Secret": settings.telegram_webhook_secret})
    except Exception as exc:
        logger.warning(f"Could not wake the announcement sender: {exc!r}")


async def send_telegram_message(telegram_id: int, text: str, *, refresh_menu: bool = False) -> bool:
    """
    Sends a Telegram message to a user via the Bot HTTP API.
    Returns True on success, False on failure (never raises).

    refresh_menu=True is for plan changes (PRO, dual degree, full access): the bot
    relay reloads the user's profile and attaches the matching main menu, so buttons
    like "Upgrade to PRO" / "Switch Department" change the moment the message arrives.
    Sending directly (no BOT_NOTIFY_URL) delivers the text only.
    """
    if settings.bot_notify_url:
        return await _send_via_bot_relay(telegram_id, text, refresh_menu)

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
        logger.warning(f"Telegram notify exception for telegram_id={telegram_id}: {exc!r}")
        return False
