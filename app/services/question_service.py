from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncConnection
from app.core.utils import armor_text

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
        semester: str | None = None,
        course_name_search: str | None = None,
        mode: Literal["exam", "practice"] = "practice",
    ) -> dict:
        """Fetch questions based on various filters of discovery."""
        
        # Select explicit columns to avoid ORM/Core confusion in raw rows
        query = (
            select(
                Question.id,
                Question.prompt,
                Question.choice_a,
                Question.choice_b,
                Question.choice_c,
                Question.choice_d,
                Question.correct_choice,
                Question.explanation_static,
                Question.course_id,
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
        if semester:
            filters.append(PastExam.semester == semester)
        if course_name_search:
            filters.append(Course.name.ilike(f"%{course_name_search}%"))

        if filters:
            query = query.where(and_(*filters))

        result = await conn.execute(query)
        rows = result.all()

        questions_list = []
        for row in rows:
            item = {
                "id": row.id,
                "prompt": armor_text(row.prompt),
                "choice_a": armor_text(row.choice_a),
                "choice_b": armor_text(row.choice_b),
                "choice_c": armor_text(row.choice_c),
                "choice_d": armor_text(row.choice_d),
                "year": row.year,
                "course_id": row.course_id,
                "course_name": row.course_name,
                "topic_name": row.topic_name,
            }
            
            if mode == "practice":
                item["correct_choice"] = row.correct_choice
                item["explanation"] = armor_text(row.explanation_static)
            
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

    async def get_exams_by_department(self, conn: AsyncConnection, department_id: uuid.UUID) -> list[dict]:
        """List available years and semesters for a specific department."""
        query = (
            select(PastExam.year, PastExam.semester)
            .where(PastExam.department_id == department_id)
            .distinct()
            .order_by(PastExam.year.desc())
        )
        result = await conn.execute(query)
        return [{"year": row.year, "semester": row.semester} for row in result]
