from __future__ import annotations

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

from langchain_core.tools import tool
from sqlalchemy import select

from app.db.postgres import db_conn
from app.models.question import Question
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic


class QuestionDetailsInput(BaseModel):
    question_id: UUID = Field(description="The UUID of the question to retrieve.")

class UserWeakTopicsInput(BaseModel):
    user_id: UUID = Field(description="The UUID of the user to get weak topics for.")


@tool(args_schema=QuestionDetailsInput)
async def get_question_details(question_id: UUID) -> dict[str, Any]:
    """
    Retrieves details of a specific question by its ID.
    """
    async with db_conn(telegram_id=None) as conn:
        # Use execute().fetchone() to get the whole row as a model-like object
        # With SQLAlchemy 2.0 and AsyncConnection, select(Question) returns all columns
        result = await conn.execute(select(Question).where(Question.id == question_id))
        question = result.fetchone()
        
        if question:
            # Result rows can be accessed as attributes
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

@tool(args_schema=UserWeakTopicsInput)
async def get_user_weak_topics(user_id: UUID) -> list[dict[str, Any]]:
    """
    Retrieves a list of topics where the user has made the most errors.
    """
    async with db_conn(telegram_id=None) as conn:
        query = select(
            UserTopicError.topic_id,
            Topic.name.label("topic_name"),
            UserTopicError.error_count
        ).join(Topic, UserTopicError.topic_id == Topic.id).where(UserTopicError.user_id == user_id).order_by(UserTopicError.error_count.desc()).limit(5)
        
        result = await conn.execute(query)
        weak_topics = []
        for row in result:
            weak_topics.append({
                "topic_id": str(row.topic_id), 
                "topic_name": row.topic_name, 
                "error_count": row.error_count
            })
        return weak_topics
