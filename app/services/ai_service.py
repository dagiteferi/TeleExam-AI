from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from app.models.user import User
from app.ai.graph import AiGraph
from app.ai.tools import get_question_details, get_user_weak_topics
from app.schemas.ai import ExplainResponse, ChatResponse, StudyPlanResponse, StudyPlanDetails, StudyPlanTopic
from app.core.utils import armor_text


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
        question_details = await get_question_details.ainvoke({"question_id": question_id})
        if not question_details:
            return ExplainResponse(success=False, explanation="Question context unavailable.")

        # Tell the AI to analyze and generate the response explicitly
        prompt_message = (
            f"Please analyze the following question and provide your powerful, structured single-paragraph explanation:\n\n"
            f"Question: {question_details['prompt']}\n"
            f"Choices: A) {question_details['choice_a']}, B) {question_details['choice_b']}, "
            f"C) {question_details['choice_c']}, D) {question_details['choice_d']}\n"
            f"Correct Answer: {question_details['correct_choice']}\n"
            f"Student's Answer: {user_answer if user_answer else 'None'}"
        )
        
        result = await self.ai_graph.invoke(prompt_message, config={"configurable": {"session_id": str(telegram_id)}})
        explanation_text = result["messages"][-1].content if result and result["messages"] else "I'm having trouble generating an explanation right now."

        # Simple extraction of key points or generic relevant ones for now
        # Ideally, the AI graph would return a structured response.
        return ExplainResponse(
            success=True,
            explanation=armor_text(explanation_text),
            key_points=["Conceptual Analysis", "Correct Application"],
            weak_topic_suggestion=f"Review concepts related to {question_details[ 'topic_name' ]}" if 'topic_name' in question_details else "General review"
        )

    async def chat(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        message: str,
        question_id: UUID | None = None,
    ) -> ChatResponse:
        context_prefix = ""
        if question_id:
            q_details = await get_question_details.ainvoke({"question_id": question_id})
            if q_details:
                context_prefix = (
                    f"CONTEXT: We are discussing this question: '{q_details['prompt']}'. "
                    f"Choice A: {q_details['choice_a']}, Choice B: {q_details['choice_b']}, "
                    f"Choice C: {q_details['choice_c']}, Choice D: {q_details['choice_d']}. "
                    f"Correct Answer: {q_details['correct_choice']}.\n\nUSER QUESTION: "
                )

        full_message = f"{context_prefix}{message}"
        result = await self.ai_graph.invoke(full_message, config={"configurable": {"session_id": str(telegram_id)}})
        
        ai_response_text = result["messages"][-1].content if result and result["messages"] else "I'm sorry, I couldn't respond to that."

        return ChatResponse(
            success=True,
            ai_response=armor_text(ai_response_text)
        )

    async def generate_study_plan(
        self,
        conn: AsyncConnection,
        telegram_id: int,
    ) -> StudyPlanResponse:
        # Fetch user UUID from telegram_id
        user_id = await conn.scalar(select(User.id).where(User.telegram_id == telegram_id))
        if not user_id:
            return StudyPlanResponse(success=False, study_plan=StudyPlanDetails(title="User not found", duration_days=0, topics=[]))

        weak_topics_data = await get_user_weak_topics.ainvoke({"user_id": user_id})
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
