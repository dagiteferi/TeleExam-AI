from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.ai import ExplainResponse, ChatResponse
from app.models.ai_study_plan import StudyPlanResponse, StudyPlanDetails, StudyPlanTopic

class AiService:
    async def explain_question(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        question_id: int,
        user_answer: str | None,
    ) -> ExplainResponse:
        # Dummy explanation logic
        return ExplainResponse(
            success=True,
            explanation=f"Here is a detailed explanation for question {question_id}.",
            key_points=["Point 1", "Point 2"],
            weak_topic_suggestion="Review Algorithm Basics"
        )

    async def chat(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        message: str,
    ) -> ChatResponse:
        # Dummy chat logic
        return ChatResponse(
            success=True,
            ai_response="Let's break down your question. What specifically are you struggling with?"
        )

    async def generate_study_plan(
        self,
        conn: AsyncConnection,
        telegram_id: int,
    ) -> StudyPlanResponse:
        return StudyPlanResponse(
            success=True,
            study_plan=StudyPlanDetails(
                title="Personalized Study Plan",
                duration_days=7,
                topics=[
                    StudyPlanTopic(
                        name="Basic AI concepts",
                        resources=["URL 1", "URL 2"]
                    )
                ]
            )
        )
