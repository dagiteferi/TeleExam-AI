from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

class AnalyticsService:
    async def record_user_topic_error(
        self, conn: AsyncConnection, user_id: UUID, topic_id: UUID
    ) -> None:
        pass

from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic

class AnalyticsService:
    async def record_user_topic_error(
        self, conn: AsyncConnection, user_id: UUID, topic_id: UUID
    ) -> None:
        stmt = pg_insert(UserTopicError).values(
            user_id=user_id,
            topic_id=topic_id,
            error_count=1
        ).on_conflict_do_update(
            index_elements=["user_id", "topic_id"],
            set_={"error_count": UserTopicError.error_count + 1}
        )
        await conn.execute(stmt)

    async def record_user_topic_errors(
        self, conn: AsyncConnection, user_id: UUID, error_counts: dict[UUID, int]
    ) -> None:
        """Same as record_user_topic_error, for many topics in one statement."""
        if not error_counts:
            return
        stmt = pg_insert(UserTopicError).values([
            {"user_id": user_id, "topic_id": topic_id, "error_count": count}
            for topic_id, count in error_counts.items()
        ])
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "topic_id"],
            set_={"error_count": UserTopicError.error_count + stmt.excluded.error_count}
        )
        await conn.execute(stmt)

    async def get_weak_topics_for_user(
        self, conn: AsyncConnection, user_id: UUID
    ) -> list[dict]:
        query = (
            select(Topic.name, UserTopicError.error_count)
            .join(UserTopicError, Topic.id == UserTopicError.topic_id)
            .where(UserTopicError.user_id == user_id)
            .order_by(UserTopicError.error_count.desc())
            .limit(5)
        )
        result = await conn.execute(query)
        return [{"topic_name": row.name, "error_count": row.error_count} for row in result]
