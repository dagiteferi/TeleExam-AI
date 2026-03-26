from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select

from app.db.postgres import db_conn
from app.models.question import Question
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic


@tool
async def get_question_details(question_id: UUID, conn: AsyncConnection) -> dict[str, Any]:
    async with db_conn(telegram_id=None) as conn:
        question = await conn.scalar(select(Question).where(Question.id == question_id))
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
        return {}

@tool
async def get_user_weak_topics(user_id: UUID, conn: AsyncConnection) -> list[dict[str, Any]]:
    async with db_conn(telegram_id=None) as conn:
        query = select(
            UserTopicError.topic_id,
            Topic.name.label("topic_name"),
            UserTopicError.error_count
        ).join(Topic, UserTopicError.topic_id == Topic.id).where(UserTopicError.user_id == user_id).order_by(UserTopicError.error_count.desc()).limit(5)
        
        result = await conn.execute(query)
        weak_topics = [{"topic_id": str(row.topic_id), "topic_name": row.topic_name, "error_count": row.error_count} for row in result]
        return weak_topics
