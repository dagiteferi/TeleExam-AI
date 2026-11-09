from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID
import json

from sqlalchemy import select, func, true, or_
from app.models.user import User
from app.models.department import Department
from app.models.exam_result import ExamResult
from app.models.course import Course
from app.services.access_service import AccessService
from app.services.analytics_service import AnalyticsService
from app.services.invitation_service import InvitationService
from app.services import mistakes_trial
from app.ai.graph import AiGraph
from app.ai.tools import fetch_question_details, fetch_user_weak_topics
from app.schemas.ai import (
    ExplainResponse, ChatResponse,
    StudyPlanResponse, StudyPlanDetails, StudyTopic, StudyDay
)
from app.core.config import settings
from app.core.utils import armor_text
from redis.asyncio import Redis
from app.db.redis import get_ai_usage_key, get_active_session_key, get_session_key

# Singleton: built once at startup, shared by all concurrent requests with active model
_ai_graph = AiGraph()


FREE_AI_DAILY_LIMIT = 5
MIN_ANSWERS_FOR_PLAN = 10  # fewer answers than this cannot show reliable weak areas

PRO_UPGRADE_LINE = (
    f"Upgrade to PRO for {settings.PRO_PRICE_BIRR} Birr to unlock all features: "
    "unlimited AI Tutor, all past exams and personalized study plans."
)

# PRO features are unlocked by a paid PRO plan or by admin-granted full access.
_HAS_PRO = or_(User.is_pro.is_(True), User.is_full_access.is_(True)).label("is_pro")

def _focus_for_rate(error_rate_percent: float) -> str:
    if error_rate_percent >= 60:
        return "High Priority"
    if error_rate_percent >= 40:
        return "Medium"
    return "Review"


# Older bot versions send this instead of omitting question_id for general chat.
GENERAL_CHAT_QUESTION_ID = "00000000-0000-0000-0000-000000000000"


async def _consume_free_ai_use(redis: Redis, usage_key: str, daily_limit: int = FREE_AI_DAILY_LIMIT) -> bool:
    """Atomically uses one free AI request; False once the daily limit is reached."""
    used = await redis.incr(usage_key)
    if used == 1:
        await redis.expire(usage_key, 86400)  # Reset after 24 hours
    if used > daily_limit:
        await redis.decr(usage_key)  # Blocked attempts don't count
        return False
    return True


EXAM_LOCKED_MESSAGE = "🔒 AI Tutor is not available during an exam. Finish the exam first, then ask the AI."


async def _in_running_exam(redis: Redis, user_id: UUID, question_id: UUID | str) -> bool:
    """True when the question is part of the user's exam that is still in progress (AI must not give answers)."""
    session_id = await redis.get(get_active_session_key(user_id, "exam"))
    if not session_id:
        return False
    status, question_ids = await redis.hmget(get_session_key(session_id), "status", "question_ids")
    if status != "in_progress" or not question_ids:
        return False
    try:
        qid = str(UUID(str(question_id)))
    except ValueError:
        return False
    return qid in json.loads(question_ids)


async def _release_db(conn: AsyncConnection) -> None:
    """
    Returns the request's DB connection to the pool before the slow LLM call.
    Everything the prompt needs is already loaded, so the AI call doesn't need the DB;
    holding the connection for the whole call would let a few AI requests exhaust the pool.
    """
    await conn.close()


async def _refund_free_ai_use(redis: Redis, usage_key: str | None) -> None:
    """Gives back a free AI request that failed before producing an answer."""
    if usage_key:
        await redis.decr(usage_key)


class AiService:
    def __init__(self):
        # Reuse the module-level singleton instead of building a new graph per request
        self.ai_graph = _ai_graph

    async def explain_question(
        self,
        conn: AsyncConnection,
        redis: Redis,
        telegram_id: int,
        question_id: UUID,
        user_answer: str | None,
        source: str | None = None,
    ) -> ExplainResponse:
        # --- Referral & Usage Check ---
        user_row = await conn.execute(select(User.id, User.invite_count, _HAS_PRO).where(User.telegram_id == telegram_id))
        user = user_row.fetchone()

        if not user:
             return ExplainResponse(success=False, explanation="User profile not found.")

        # Anti-cheat: never explain a question of the exam the user is taking right now
        if await _in_running_exam(redis, user.id, question_id):
            return ExplainResponse(success=False, explanation=EXAM_LOCKED_MESSAGE)

        usage_key = None
        mistakes_trial_used = False
        if not user.is_pro and source == "mistakes":
            # Review My Mistakes free trial: its own small lifetime allowance, then PRO
            if not await mistakes_trial.consume_ai(redis, telegram_id):
                return ExplainResponse(
                    success=False,
                    explanation=f"🔒 You've used your free AI explanation in Review My Mistakes.\n\n{PRO_UPGRADE_LINE}",
                )
            mistakes_trial_used = True
        elif not user.is_pro:
            invite_config = await InvitationService.get_config(conn)
            daily_limit = invite_config.calculate_ai_daily_limit(user.invite_count or 0, base_limit=FREE_AI_DAILY_LIMIT)
            usage_key = get_ai_usage_key(telegram_id)
            if not await _consume_free_ai_use(redis, usage_key, daily_limit=daily_limit):
                return ExplainResponse(success=False, explanation=f"⚠️ You've used your {daily_limit} free AI explanations for today!\n\n{PRO_UPGRADE_LINE}")
        # ------------------------------

        # SECURE: Pass student's telegram_id to activate RLS for fetch_question_details
        question_details = await fetch_question_details(question_id, conn=conn)
        await _release_db(conn)
        if not question_details:
            await _refund_free_ai_use(redis, usage_key)
            if mistakes_trial_used:
                await mistakes_trial.refund_ai(redis, telegram_id)
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
        
        try:
            result = await self.ai_graph.invoke(prompt_message, instructions, config={"configurable": {"session_id": str(telegram_id)}})
        except Exception:
            await _refund_free_ai_use(redis, usage_key)
            if mistakes_trial_used:
                await mistakes_trial.refund_ai(redis, telegram_id)
            raise
        explanation_text = result["messages"][-1].content if result and result["messages"] else "Explanation generation failed."
        if mistakes_trial_used and (not explanation_text or explanation_text.startswith("⚠️")):
            # AiGraph returns its "⚠️ AI ... unavailable" text instead of raising: don't spend
            # the only free trial explanation on a failure.
            await mistakes_trial.refund_ai(redis, telegram_id)
            return ExplainResponse(success=False, explanation=explanation_text or "⚠️ AI is temporarily unavailable.")

        return ExplainResponse(
            success=True,
            explanation=armor_text(explanation_text, telegram_id),
            key_points=["Conceptual Analysis", "Logical Deduction"],
            weak_topic_suggestion=f"Review concepts related to {question_details.get('topic_name', 'this area')}"
        )

    async def chat(
        self,
        conn: AsyncConnection,
        redis: Redis,
        telegram_id: int,
        message: str,
        question_id: str | None,
    ) -> ChatResponse:
        # --- Referral & Usage Check ---
        user_row = await conn.execute(select(User.id, User.invite_count, _HAS_PRO).where(User.telegram_id == telegram_id))
        user = user_row.fetchone()

        if not user:
             return ChatResponse(success=False, ai_response="User profile not found.")

        # Anti-cheat: no follow-up questions about the exam the user is taking right now
        if question_id and question_id != GENERAL_CHAT_QUESTION_ID and await _in_running_exam(redis, user.id, question_id):
            return ChatResponse(success=False, ai_response=EXAM_LOCKED_MESSAGE)

        # Follow-up questions have their own daily allowance, separate from
        # explanations, so the explanation doesn't use up a follow-up.
        usage_key = None
        if not user.is_pro:
            invite_config = await InvitationService.get_config(conn)
            daily_limit = invite_config.calculate_ai_daily_limit(user.invite_count or 0, base_limit=FREE_AI_DAILY_LIMIT)
            usage_key = f"{get_ai_usage_key(telegram_id)}:chat"
            if not await _consume_free_ai_use(redis, usage_key, daily_limit=daily_limit):
                return ChatResponse(success=False, ai_response=f"⚠️ You've used your {daily_limit} free AI follow-up questions for today!\n\n{PRO_UPGRADE_LINE}")
        # ------------------------------

        if not question_id or question_id == GENERAL_CHAT_QUESTION_ID:
            # General study chat (AI Tutor from the main menu): no question context.
            access = await AccessService.get_by_telegram_id(conn, telegram_id)
            dept_id = access.effective_department_id if access else None
            department = (
                await conn.scalar(select(Department.name).where(Department.id == dept_id)) if dept_id else None
            )
            instructions = (
                "You are a friendly study tutor for Ethiopian university students"
                + (f" in the {department} department" if department else "")
                + ". Answer the student's study question clearly and simply in 3-6 sentences, "
                "using a short example when it helps. If the message is not about studying, "
                "politely say you can only help with study questions."
            )
            full_message = message
        else:
            # SECURE: Pass student's telegram_id to activate RLS for fetch_question_details
            q_details = await fetch_question_details(question_id, conn=conn)
            if not q_details:
                await _refund_free_ai_use(redis, usage_key)
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

        await _release_db(conn)
        try:
            result = await self.ai_graph.invoke(full_message, instructions, config={"configurable": {"session_id": str(telegram_id)}})
        except Exception:
            await _refund_free_ai_use(redis, usage_key)
            raise
        
        ai_response_text = result["messages"][-1].content if result and result["messages"] else "Response generation failed."

        return ChatResponse(
            success=True,
            ai_response=armor_text(ai_response_text, telegram_id)
        )

    async def generate_study_plan(
        self,
        conn: AsyncConnection,
        redis: Redis,
        telegram_id: int,
    ) -> StudyPlanResponse:
        user_stmt = select(User.id, _HAS_PRO).where(User.telegram_id == telegram_id)
        user_row = await conn.execute(user_stmt)
        user = user_row.fetchone()
        
        if not user:
            return StudyPlanResponse(success=False, message="User session invalid.")

        # 1. Paywall: Check PRO status first
        if not user.is_pro:
            return StudyPlanResponse(
                success=False,
                message=f"💎 Upgrade to PRO: Personalized AI Study Plans are an exclusive PRO feature!\n\n{PRO_UPGRADE_LINE}"
            )

        # Dual-degree students get a plan for the department they are studying now.
        access = await AccessService.get_by_user_id(conn, user.id)
        dept_id = access.effective_department_id if access else None
        in_dept = (Course.department_id == dept_id) if dept_id else true()

        # 2. Requirement: Must have finished at least one full exam
        exam_stmt = (
            select(func.count(ExamResult.id))
            .join(Course, ExamResult.course_id == Course.id)
            .where(ExamResult.user_id == user.id, ExamResult.mode == "exam", in_dept)
        )
        exam_count = (await conn.execute(exam_stmt)).scalar() or 0
        if exam_count == 0:
             return StudyPlanResponse(success=False, message="📊 Data Needed: Please complete at least one full Mock Exam so the AI can analyze your weak points!")

        # 3. Fetch overall performance summary (aggregated across all exams)
        overall_row = await conn.execute(
            select(
                func.count(ExamResult.id).label("exam_count"),
                func.avg(ExamResult.score_percent).label("avg_score"),
                func.sum(ExamResult.correct_count).label("total_correct"),
                func.sum(ExamResult.wrong_count).label("total_wrong")
            )
            .join(Course, ExamResult.course_id == Course.id)
            .where(ExamResult.user_id == user.id, ExamResult.mode == "exam", in_dept)
        )
        overall = overall_row.fetchone()

        # 4. Current weak topics: worst error rate over each topic's recent answers
        analytics = AnalyticsService()
        weak_topics_data = await analytics.get_weak_topics(conn, user.id, dept_id, limit=6)
        # Topics are small, so early on no single topic has enough answers to judge.
        # Fall back to whole courses rather than wrongly telling the student all is well.
        by_course = False
        if not weak_topics_data:
            weak_topics_data = await analytics.get_weak_courses(conn, user.id, dept_id, limit=6)
            by_course = bool(weak_topics_data)

        if not weak_topics_data:
            answered = await analytics.count_answers(conn, user.id, dept_id)
            if answered < MIN_ANSWERS_FOR_PLAN:
                message = (
                    f"Not enough data yet. You have answered {answered} question"
                    f"{'' if answered == 1 else 's'}; answer at least {MIN_ANSWERS_FOR_PLAN} "
                    "in Practice or Exam Mode so your weak areas can be identified."
                )
            else:
                message = (
                    "No weak areas right now: you are answering most questions correctly. "
                    "Keep practising; a plan will appear here if a topic or course starts slipping."
                )
            return StudyPlanResponse(success=False, message=message)

        avg_score = float(overall.avg_score or 0)
        exam_count = int(overall.exam_count or 0)
        total_wrong = int(overall.total_wrong or 0)

        # 5. Build a compact, token-efficient data context for the AI
        topic_lines = ", ".join([
            f"{t['topic_name']}({t['wrong']}/{t['attempted']} wrong, {t['error_rate_percent']:.0f}%)"
            for t in weak_topics_data
        ])
        area = "WeakCourses" if by_course else "WeakTopics"
        ai_context = (
            f"Exams:{exam_count}, AvgScore:{avg_score:.1f}%, WrongAnswers:{total_wrong}. "
            f"{area}(name, recent wrong/attempted, error rate): {topic_lines}."
        )
        if by_course:
            ai_context += " (Too few answers per topic yet, so the weak areas are whole courses; use them as the topics.)"

        instructions = (
            "You are a study plan generator. Based on the student's exam performance data, "
            "output ONLY valid JSON in this exact structure, no extra text:\n"
            '{"summary": "1-2 sentence performance summary", '
            '"weak_topics": [{"topic": "TopicName", "errors": N, "focus": "High Priority|Medium|Review"}], '
            '"daily_plan": [{"day": 1, "topic": "TopicName", "action": "What to do"}]}\n'
            "Rules: focus = High Priority if error rate>=60%, Medium if 40-59%, Review if <40%. "
            "Spend more days on higher error rates. "
            "Create a 7-day plan cycling through the top weak topics. Be concise."
        )

        await _release_db(conn)
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
                    topic=t["topic_name"],
                    errors=t["wrong"],
                    focus=_focus_for_rate(t["error_rate_percent"]),
                )
                for t in weak_topics_data
            ]
            daily_plan = [
                StudyDay(day=i + 1, topic=weak_topics[i % len(weak_topics)].topic, action="Review notes and solve past questions")
                for i in range(7)
            ]
            summary = f"You averaged {avg_score:.1f}% across {exam_count} exam(s). Focus on the topics below."

        plan_details = StudyPlanDetails(
            summary=summary,
            total_exams_done=exam_count,
            overall_score_percent=round(avg_score, 1),
            weak_topics=weak_topics,
            daily_plan=daily_plan,
            total_hours_needed=10 + (len(weak_topics) * 3)
        )

        return StudyPlanResponse(
            success=True,
            study_plan=plan_details,
            message="Your Diagnostic Study Plan has been generated! Use this roadmap to focus your preparation."
        )

