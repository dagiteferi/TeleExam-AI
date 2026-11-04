import json
from uuid import UUID
from typing import Any
from pydantic import BaseModel, Field

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.postgres import db_conn
from app.models.question import Question
from app.models.user import User
from app.services.access_service import AccessService
from app.services.analytics_service import AnalyticsService


# Internal Fetchers with Identity Hardening (Passes telegram_id for RLS enforcement)
async def fetch_question_details(
    question_id: UUID, telegram_id: int | None = None, conn: AsyncConnection | None = None
) -> dict[str, Any] | None:
    # Reuse the caller's connection when given, so a request doesn't hold two pool connections
    if conn is None:
        async with db_conn(telegram_id=telegram_id) as own_conn:
            return await fetch_question_details(question_id, conn=own_conn)

    result = await conn.execute(select(Question).where(Question.id == question_id))
    question = result.fetchone()
    if question:
        return {
            "question_id": str(question.id),
            "prompt": question.prompt,
            "choice_a": question.choice_a,
            "choice_b": question.choice_b,
            "choice_c": question.choice_c,
            "choice_d": question.choice_d,
            "correct_choice": question.correct_choice,
            "explanation_static": question.explanation_static,
        }
    return None

async def fetch_user_weak_topics(user_id: UUID, telegram_id: int | None = None) -> list[dict[str, Any]]:
    """Current weak topics (recent error rate) in the department the student is studying now."""
    async with db_conn(telegram_id=telegram_id) as conn:
        access = await AccessService.get_by_user_id(conn, user_id)
        dept_id = access.effective_department_id if access else None
        return await AnalyticsService().get_weak_topics(conn, user_id, dept_id, limit=5)


# SECURE AI TOOLS (Zero-parameter to bypass model spoofing risks)
@tool
async def get_my_weak_topics(config: RunnableConfig) -> str:
    """
    Retrieves the current student's top weak topics based on their error history.
    This tool is identity-secure and strictly tied to the student's authenticated session.
    """
    telegram_id_str = config["configurable"].get("session_id")
    if not telegram_id_str:
         return "Error: Session context missing."
    
    try:
        telegram_id = int(telegram_id_str)
        # 1. Fetch current user context securely using telegram_id (RLS Active)
        async with db_conn(telegram_id=telegram_id) as conn:
            user_id = await conn.scalar(select(User.id).where(User.telegram_id == telegram_id))
            if not user_id:
                return "Error: User context not authenticated."
            
            # 2. Re-verify topics under students's specific security context
            topics = await fetch_user_weak_topics(user_id, telegram_id=telegram_id)
            return json.dumps(topics)
    except Exception as e:
        return f"Error: Data retrieval blocked or failed."
