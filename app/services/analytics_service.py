from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

class AnalyticsService:
    async def record_user_topic_error(
        self, conn: AsyncConnection, user_id: UUID, topic_id: UUID
    ) -> None:
        pass

    async def get_weak_topics_for_user(
        self, conn: AsyncConnection, user_id: UUID
    ) -> list[dict]:
        return []
