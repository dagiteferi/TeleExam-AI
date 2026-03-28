from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

class ScoringService:
    async def compute_session_score(
        self, conn: AsyncConnection, session_id: UUID, user_id: UUID, answers: dict
    ) -> dict:
        return {"correct_count": 0, "wrong_count": 0, "score_percent": 0.0}

    async def persist_exam_results(
        self, conn: AsyncConnection, user_id: UUID, session_id: UUID, score_data: dict
    ) -> None:
        pass
