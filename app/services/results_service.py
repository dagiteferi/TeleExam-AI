from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.results import OverallResultsResponse, SessionResultResponse

class ResultsService:
    async def get_overall_results(
        self,
        conn: AsyncConnection,
        telegram_id: int,
    ) -> OverallResultsResponse:
        # Dummy data for now
        return OverallResultsResponse(
            success=True,
            total_exams_taken=10,
            average_score=75.5,
            weak_topics=["Algebra", "Data Structures"],
            recent_sessions=[],
        )

    async def get_session_results(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        session_id: str,
    ) -> SessionResultResponse:
        # Dummy data for now
        return SessionResultResponse(
            success=True,
            session_id=session_id,
            mode="exam",
            score=70,
            total_questions=10,
            correct_answers=7,
            incorrect_answers=3,
            questions_details=[],
        )
