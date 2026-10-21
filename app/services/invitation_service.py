from __future__ import annotations

import datetime
import json
import time
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.app_setting import AppSetting
from app.schemas.invitation import (
    InvitationRuleConfig,
    InvitationRuleResponse,
    InvitationRuleUpdate,
)

logger = structlog.get_logger(__name__)

INVITATION_SETTINGS_KEY = "invitation_rules"
_CACHE_TTL_SECONDS = 60.0


class _InvitationCache:
    def __init__(self) -> None:
        self.config: InvitationRuleConfig | None = None
        self.updated_at: datetime.datetime | None = None
        self.cached_at: float = 0.0

    def is_valid(self) -> bool:
        return self.config is not None and (time.time() - self.cached_at) < _CACHE_TTL_SECONDS

    def set(self, config: InvitationRuleConfig, updated_at: datetime.datetime | None = None) -> None:
        self.config = config
        self.updated_at = updated_at or datetime.datetime.now(datetime.timezone.utc)
        self.cached_at = time.time()

    def clear(self) -> None:
        self.config = None
        self.updated_at = None
        self.cached_at = 0.0


_cache = _InvitationCache()


class InvitationService:
    @staticmethod
    def invalidate_cache() -> None:
        """Flushes the local in-memory configuration cache."""
        _cache.clear()

    @classmethod
    async def get_config(cls, conn: AsyncConnection | None = None) -> InvitationRuleConfig:
        """
        Retrieves the active invitation rule configuration.
        Utilizes a short-lived in-memory cache to prevent redundant DB lookups.
        """
        if _cache.is_valid() and _cache.config is not None:
            return _cache.config

        if conn is None:
            from app.db.postgres import db_conn
            async with db_conn(telegram_id=None) as db:
                return await cls._fetch_from_db(db)

        return await cls._fetch_from_db(conn)

    @classmethod
    async def get_response(cls, conn: AsyncConnection | None = None) -> InvitationRuleResponse:
        """Retrieves active configuration packaged into an admin response with summary."""
        config = await cls.get_config(conn)
        return InvitationRuleResponse(
            **config.model_dump(),
            summary=config.get_summary(),
            updated_at=_cache.updated_at,
        )

    @classmethod
    async def update_config(
        cls,
        conn: AsyncConnection,
        payload: InvitationRuleConfig | InvitationRuleUpdate,
    ) -> InvitationRuleResponse:
        """
        Persists updated invitation rules to app_settings and refreshes the cache.
        """
        current = await cls.get_config(conn)

        if isinstance(payload, InvitationRuleUpdate):
            update_data = payload.model_dump(exclude_unset=True)
            merged_dict = {**current.model_dump(), **update_data}
            updated_config = InvitationRuleConfig(**merged_dict)
        else:
            updated_config = payload

        now = datetime.datetime.now(datetime.timezone.utc)
        json_val = updated_config.model_dump_json()

        stmt = (
            pg_insert(AppSetting)
            .values(
                key=INVITATION_SETTINGS_KEY,
                value=json_val,
                description=(
                    "Configurable rules for referral invitations: exam years unlocked per invite, "
                    "free baseline years, courses ratio, and universal unlock threshold."
                ),
                is_public=True,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "value": json_val,
                    "updated_at": now,
                    "is_public": True,
                },
            )
            .returning(AppSetting.updated_at)
        )

        result = await conn.execute(stmt)
        row = result.fetchone()
        updated_at = row[0] if row else now

        _cache.set(updated_config, updated_at)
        logger.info(
            "Updated invitation configuration",
            summary=updated_config.get_summary(),
            config=updated_config.model_dump(),
        )

        return InvitationRuleResponse(
            **updated_config.model_dump(),
            summary=updated_config.get_summary(),
            updated_at=updated_at,
        )

    @classmethod
    async def _fetch_from_db(cls, conn: AsyncConnection) -> InvitationRuleConfig:
        try:
            stmt = select(AppSetting.value, AppSetting.updated_at).where(
                AppSetting.key == INVITATION_SETTINGS_KEY
            )
            res = await conn.execute(stmt)
            row = res.fetchone()

            if row and row[0]:
                raw_json = json.loads(row[0])
                config = InvitationRuleConfig(**raw_json)
                _cache.set(config, row[1])
                return config

            # Fallback: check if individual keys exist
            fallback_keys = [
                "free_years",
                "invites_per_year",
                "years_per_invite",
                "invites_to_unlock_all_years",
                "free_courses_ratio",
                "invites_to_unlock_all_courses",
                "invites_to_unlock_all",
                "ai_bonus_per_invite",
            ]
            fb_stmt = select(AppSetting.key, AppSetting.value).where(AppSetting.key.in_(fallback_keys))
            fb_res = await conn.execute(fb_stmt)
            fb_rows = dict(fb_res.fetchall())

            if fb_rows:
                merged: dict[str, Any] = {}
                for k, v in fb_rows.items():
                    if v is not None:
                        try:
                            merged[k] = float(v) if "." in v else int(v)
                        except ValueError:
                            pass
                config = InvitationRuleConfig(**merged)
                _cache.set(config, None)
                return config

        except Exception as exc:
            logger.warning("Failed to load invitation_rules from DB; using default fallback", error=str(exc))

        default_config = InvitationRuleConfig()
        _cache.set(default_config, None)
        return default_config
