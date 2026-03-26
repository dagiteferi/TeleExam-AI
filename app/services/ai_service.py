from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

from langchain_core.messages import HumanMessage
from app.ai.graph import AiGraph
from app.ai.tools import get_question_details, get_user_weak_topics
from app.schemas.ai import ExplainResponse, ChatResponse, StudyPlanResponse, StudyPlanDetails, StudyPlanTopic


class AiService:
    def __init__(self):
        self.ai_graph = AiGraph()

    async def explain_question(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        question_id: UUID,
        user_answer: str | None,
    ) -> ExplainResponse:
        question_details = await get_question_details.ainvoke({"question_id": question_id, "conn": conn})
        if not question_details:
            return ExplainResponse(success=False, explanation="Question not found.")

        prompt_message = (
            f"Explain question {question_details['question_id']}: '{question_details['prompt']}'. "
            f"Choices: A) {question_details['choice_a']}, B) {question_details['choice_b']}, "
            f"C) {question_details['choice_c']}, D) {question_details['choice_d']}. "
            f"User answered: {user_answer}. Correct answer: {question_details['correct_choice']}."
        )
        
        result = await self.ai_graph.invoke(prompt_message, config={"configurable": {"session_id": str(telegram_id)}})
        
        explanation_text = result["messages"][-1].content if result and result["messages"] else "No explanation generated."

        return ExplainResponse(
            success=True,
            explanation=explanation_text,
            key_points=["Point 1", "Point 2"],
            weak_topic_suggestion="Review Algorithm Basics"
        )

    async def chat(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        message: str,
    ) -> ChatResponse:
        result = await self.ai_graph.invoke(message, config={"configurable": {"session_id": str(telegram_id)}})
        
        ai_response_text = result["messages"][-1].content if result and result["messages"] else "No response generated."

        return ChatResponse(
            success=True,
            ai_response=ai_response_text
        )

    async def generate_study_plan(
        self,
        conn: AsyncConnection,
        telegram_id: int,
    ) -> StudyPlanResponse:
        weak_topics_data = await get_user_weak_topics.ainvoke({"user_id": telegram_id, "conn": conn})
        weak_topics_names = [topic["topic_name"] for topic in weak_topics_data]

        prompt_message = f"Generate a study plan for the following weak topics: {', '.join(weak_topics_names)}. The user wants to study for 7 days."
        
        result = await self.ai_graph.invoke(prompt_message, config={"configurable": {"session_id": str(telegram_id)}})
        
        study_plan_content = result["messages"][-1].content if result and result["messages"] else "{}"
        
        try:
            study_plan_details = StudyPlanDetails.model_validate_json(study_plan_content)
        except Exception:
            study_plan_details = StudyPlanDetails(
                title="Generated Study Plan",
                duration_days=7,
                topics=[StudyPlanTopic(name="Review weak topics", resources=[])]
            )

        return StudyPlanResponse(
            success=True,
            study_plan=study_plan_details
        )
