from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from app.models.user import User
from app.ai.graph import AiGraph
from app.ai.tools import fetch_question_details, fetch_user_weak_topics
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
        # Use fetch_question_details (raw dict) for the service layer
        question_details = await fetch_question_details(question_id)
        if not question_details:
            return ExplainResponse(success=False, explanation="Question context unavailable.")

        # Pedagogical instructions for a deep, single-paragraph explanation
        instructions = (
            "You are a professional exam assistant. Provide a single, cohesive pedagogical paragraph. "
            "Explain exactly: (1) what the question asks, (2) the core concept, (3) why the correct answer is right, "
            "and (4) why other choices are wrong. No labels. 5-8 sentences. Deep and smooth text."
        )

        prompt_message = (
            f"Question: {question_details['prompt']}\n"
            f"Choices: A) {question_details['choice_a']}, B) {question_details['choice_b']}, "
            f"C) {question_details['choice_c']}, D) {question_details['choice_d']}\n"
            f"Correct Answer: {question_details['correct_choice']}\n"
            f"Student's Answer: {user_answer if user_answer else 'None'}"
        )
        
        result = await self.ai_graph.invoke(prompt_message, instructions, config={"configurable": {"session_id": str(telegram_id)}})
        explanation_text = result["messages"][-1].content if result and result["messages"] else "Explanation generation failed."

        return ExplainResponse(
            success=True,
            explanation=armor_text(explanation_text),
            key_points=["Conceptual Analysis", "Logical Deduction"],
            weak_topic_suggestion=f"Review concepts related to {question_details.get('topic_name', 'this area')}"
        )

    async def chat(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        message: str,
        question_id: UUID,
    ) -> ChatResponse:
        # Use fetch_question_details (raw dict) for the service layer
        q_details = await fetch_question_details(question_id)
        if not q_details:
             return ChatResponse(success=False, ai_response="Question context unavailable.")

        # Interactive instructions for social tutor mode
        instructions = (
            "You are a supportive exam tutor. The user is asking a follow-up question about a specific problem. "
            "Answer their specific doubt directly and concisely based on the context provided. "
            "Do NOT repeat the entire conceptual analysis unless relevant to their specific doubt. "
            "Be encouraging and clear."
        )

        context_prefix = (
            f"CONTEXT:\nQuestion: '{q_details['prompt']}'\n"
            f"A: {q_details['choice_a']}, B: {q_details['choice_b']}, "
            f"C: {q_details['choice_c']}, D: {q_details['choice_d']}\n"
            f"Correct Answer: {q_details['correct_choice']}\n\n"
        )

        full_message = f"{context_prefix}USER QUESTION: {message}"
        result = await self.ai_graph.invoke(full_message, instructions, config={"configurable": {"session_id": str(telegram_id)}})
        
        ai_response_text = result["messages"][-1].content if result and result["messages"] else "Response generation failed."

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

        weak_topics_data = await fetch_user_weak_topics(user_id)
        weak_topics_names = [topic["topic_name"] for topic in weak_topics_data]

        prompt_message = f"Generate a study plan for the following weak topics: {', '.join(weak_topics_names)}. The user wants to study for 7 days."
        
        instructions = "You are a study coordinator. Generate a structured JSON study plan based on the user's weak topics."
        result = await self.ai_graph.invoke(prompt_message, instructions, config={"configurable": {"session_id": str(telegram_id)}})
        
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
