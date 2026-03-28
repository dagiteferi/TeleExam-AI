from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID
import json

from sqlalchemy import select, func
from app.models.user import User
from app.models.exam_result import ExamResult
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic
from app.ai.graph import AiGraph
from app.ai.tools import fetch_question_details, fetch_user_weak_topics
from app.schemas.ai import (
    ExplainResponse, ChatResponse,
    StudyPlanResponse, StudyPlanDetails, StudyTopic, StudyDay
)
from app.core.utils import armor_text

# Singleton: built once at startup, shared by all concurrent requests
_ai_graph = AiGraph()


class AiService:
    def __init__(self):
        # Reuse the module-level singleton instead of building a new graph per request
        self.ai_graph = _ai_graph

    async def explain_question(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        question_id: UUID,
        user_answer: str | None,
    ) -> ExplainResponse:
        # SECURE: Pass student's telegram_id to activate RLS for fetch_question_details
        question_details = await fetch_question_details(question_id, telegram_id=telegram_id)
        if not question_details:
            return ExplainResponse(success=False, explanation="Question context unavailable or access denied.")

        # Compact prompt: covers all 4 pedagogical steps in fewer tokens
        instructions = (
            "Write one fluent paragraph (5-7 sentences): explain the question, the concept, "
            "why the correct answer is right, and why each other choice is wrong. No headers."
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
        # SECURE: Pass student's telegram_id to activate RLS for fetch_question_details
        q_details = await fetch_question_details(question_id, telegram_id=telegram_id)
        if not q_details:
             return ChatResponse(success=False, ai_response="Question context unavailable or access denied.")

        # Compact prompt: answer the specific doubt only
        instructions = (
            "You are an exam tutor. Answer the student's doubt directly, concisely, "
            "based only on the provided question context. 2-4 sentences max."
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
        # 1. Get authenticated user
        user_id = await conn.scalar(select(User.id).where(User.telegram_id == telegram_id))
        if not user_id:
            return StudyPlanResponse(success=False, message="User session invalid.")

        # 2. PREREQUISITE CHECK: user must have completed at least one full exam
        completed_exam_count = await conn.scalar(
            select(func.count(ExamResult.id)).where(
                ExamResult.user_id == user_id,
                ExamResult.mode == "exam"
            )
        )
        if not completed_exam_count:
            return StudyPlanResponse(
                success=False,
                message=(
                    "You need to complete at least one full exam (e.g. 2015, 2016, 2017 past exam) "
                    "before I can generate a personalized study plan. "
                    "Your results help me find exactly where you need to focus."
                )
            )

        # 3. Fetch overall performance summary (aggregated across all exams)
        overall_row = await conn.execute(
            select(
                func.count(ExamResult.id).label("exam_count"),
                func.avg(ExamResult.score_percent).label("avg_score"),
                func.sum(ExamResult.correct_count).label("total_correct"),
                func.sum(ExamResult.wrong_count).label("total_wrong")
            ).where(ExamResult.user_id == user_id, ExamResult.mode == "exam")
        )
        overall = overall_row.fetchone()

        # 4. Fetch per-topic error counts (top 6 weak topics)
        topic_rows = await conn.execute(
            select(
                Topic.name,
                UserTopicError.error_count
            ).join(Topic, UserTopicError.topic_id == Topic.id)
            .where(UserTopicError.user_id == user_id)
            .order_by(UserTopicError.error_count.desc())
            .limit(6)
        )
        weak_topics_data = topic_rows.fetchall()

        if not weak_topics_data:
            return StudyPlanResponse(
                success=False,
                message="No topic error data found yet. Complete more exam questions to get an accurate study plan."
            )

        avg_score = float(overall.avg_score or 0)
        exam_count = int(overall.exam_count or 0)
        total_wrong = int(overall.total_wrong or 0)

        # 5. Build a compact, token-efficient data context for the AI
        topic_lines = ", ".join([
            f"{row.name}({row.error_count}errors)" for row in weak_topics_data
        ])
        ai_context = (
            f"Exams:{exam_count}, AvgScore:{avg_score:.1f}%, WrongAnswers:{total_wrong}. "
            f"WeakTopics(name,errors): {topic_lines}."
        )

        instructions = (
            "You are a study plan generator. Based on the student's exam performance data, "
            "output ONLY valid JSON in this exact structure, no extra text:\n"
            '{"summary": "1-2 sentence performance summary", '
            '"weak_topics": [{"topic": "TopicName", "errors": N, "focus": "High Priority|Medium|Review"}], '
            '"daily_plan": [{"day": 1, "topic": "TopicName", "action": "What to do"}]}\n'
            "Rules: focus = High Priority if errors>5, Medium if 3-5, Review if <3. "
            "Create a 7-day plan cycling through the top weak topics. Be concise."
        )

        result = await self.ai_graph.invoke(
            ai_context, instructions,
            config={"configurable": {"session_id": str(telegram_id)}}
        )
        raw = result["messages"][-1].content if result and result["messages"] else "{}"

        # 6. Parse AI JSON output into typed schema
        try:
            # Strip markdown code fences if the model wraps output
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(clean)

            weak_topics = [
                StudyTopic(topic=t["topic"], errors=t["errors"], focus=t["focus"])
                for t in data.get("weak_topics", [])
            ]
            daily_plan = [
                StudyDay(day=d["day"], topic=d["topic"], action=d["action"])
                for d in data.get("daily_plan", [])
            ]
            summary = data.get("summary", f"You scored an average of {avg_score:.1f}% across {exam_count} exam(s).")
        except Exception:
            # Graceful fallback: build plan from raw DB data without AI
            weak_topics = [
                StudyTopic(
                    topic=row.name,
                    errors=row.error_count,
                    focus="High Priority" if row.error_count > 5 else "Medium" if row.error_count >= 3 else "Review"
                )
                for row in weak_topics_data
            ]
            daily_plan = [
                StudyDay(day=i + 1, topic=weak_topics[i % len(weak_topics)].topic, action="Review notes and solve past questions")
                for i in range(7)
            ]
            summary = f"You averaged {avg_score:.1f}% across {exam_count} exam(s). Focus on the topics below."

        return StudyPlanResponse(
            success=True,
            study_plan=StudyPlanDetails(
                summary=summary,
                total_exams_done=exam_count,
                overall_score_percent=round(avg_score, 1),
                weak_topics=weak_topics,
                daily_plan=daily_plan
            ),
            message=None
        )
