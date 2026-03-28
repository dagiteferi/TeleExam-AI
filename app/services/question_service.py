from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.question import Question
from app.models.past_exam import PastExam, PastExamQuestion
from app.models.course import Course
from app.models.topic import Topic
from app.models.department import Department

class QuestionService:
    async def get_questions(
        self,
        conn: AsyncConnection,
        department_id: uuid.UUID | None = None,
        year: int | None = None,
        course_name_search: str | None = None,
        mode: Literal["exam", "practice"] = "practice",
    ) -> dict:
        """Fetch questions based on various filters of discovery."""
        
        # Base query joining necessary metadata
        # We join Question to PastExamQuestion then to PastExam to get the Year
        query = (
            select(
                Question,
                PastExam.year,
                Course.name.label("course_name"),
                Topic.name.label("topic_name")
            )
            .join(Course, Question.course_id == Course.id)
            .join(Topic, Question.topic_id == Topic.id)
            .join(PastExamQuestion, Question.id == PastExamQuestion.question_id)
            .join(PastExam, PastExamQuestion.past_exam_id == PastExam.id)
        )

        filters = []
        if department_id:
            filters.append(PastExam.department_id == department_id)
        if year:
            filters.append(PastExam.year == year)
        if course_name_search:
            # Case-insensitive partial match or exact match
            filters.append(Course.name.ilike(f"%{course_name_search}%"))

        if filters:
            query = query.where(and_(*filters))

        result = await conn.execute(query)
        rows = result.all()

        questions_list = []
        for row in rows:
            q = row.Question
            item = {
                "id": q.id,
                "prompt": q.prompt,
                "choice_a": q.choice_a,
                "choice_b": q.choice_b,
                "choice_c": q.choice_c,
                "choice_d": q.choice_d,
                "year": row.year,
                "course_id": q.course_id,
                "course_name": row.course_name,
                "topic_name": row.topic_name,
            }
            
            # For practice mode, include correct answer and explanation immediately
            if mode == "practice":
                item["correct_choice"] = q.correct_choice
                item["explanation"] = q.explanation_static
            
            questions_list.append(item)

        return {
            "questions": questions_list,
            "total_count": len(questions_list)
        }

    async def get_available_courses(self, conn: AsyncConnection) -> list[dict]:
        """Fetch all unique course names and their IDs."""
        query = select(Course.id, Course.name).where(Course.is_active == True).distinct()
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name} for row in result]

    async def get_available_departments(self, conn: AsyncConnection) -> list[dict]:
        """Fetch all active departments."""
        query = select(Department.id, Department.name).where(Department.is_active == True)
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name} for row in result]
