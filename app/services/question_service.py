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
from app.models.user import User


class QuestionService:

    async def get_questions(
        self,
        conn: AsyncConnection,
        department_id: uuid.UUID | None = None,
        year: int | None = None,
        semester: str | None = None,
        course_name_search: str | None = None,
        mode: Literal["exam", "practice"] = "practice",
        telegram_id: int | None = None,
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
                "prompt": armor_text(row.prompt, telegram_id),
                "choice_a": armor_text(row.choice_a, telegram_id),
                "choice_b": armor_text(row.choice_b, telegram_id),
                "choice_c": armor_text(row.choice_c, telegram_id),
                "choice_d": armor_text(row.choice_d, telegram_id),
                "year": row.year,
                "course_id": row.course_id,
                "course_name": row.course_name,
                "topic_name": row.topic_name,
            }
            
            if mode == "practice":
                item["correct_choice"] = row.correct_choice
                item["explanation"] = armor_text(row.explanation_static, telegram_id)
            
            questions_list.append(item)

        return {
            "questions": questions_list,
            "total_count": len(questions_list)
        }

    async def get_available_courses(self, conn: AsyncConnection, department_id: uuid.UUID | None = None) -> list[dict]:
        """Fetch unique course names and their IDs, optionally filtered by department."""
        query = select(Course.id, Course.name, Course.department_id).where(Course.is_active == True)
        if department_id:
            query = query.where(Course.department_id == department_id)
        
        query = query.distinct().order_by(Course.name.asc())
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name, "department_id": row.department_id} for row in result]

    async def get_available_departments(self, conn: AsyncConnection) -> list[dict]:
        """Fetch all active departments."""
        query = select(Department.id, Department.name).where(Department.is_active == True)
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name} for row in result]

    async def get_exams_by_department(self, conn: AsyncConnection, department_id: uuid.UUID, telegram_id: int | None = None) -> list[dict]:
        """List available years and semesters for a specific department (deduplicated)."""
        # Fetch user stats to determine unlocked tiers
        invite_count = 0
        is_pro = False
        if telegram_id:
            user_row = await conn.execute(select(User.invite_count, User.is_pro).where(User.telegram_id == telegram_id))
            user = user_row.fetchone()
            if user:
                invite_count = user.invite_count
                is_pro = user.is_pro

        # Determination of allowed years: 1 (base) + invite_count (capped at total available)
        # However, if invite_count >= 4, we unlock all.
        unlocked_count = invite_count + 1 if invite_count < 4 else 999
        if is_pro: unlocked_count = 999

        from sqlalchemy import func, cast, Text
        query = (
            select(
                PastExam.year,
                PastExam.semester,
                func.max(cast(PastExam.id, Text)).label("id")
            )
            .where(PastExam.department_id == department_id)
            .group_by(PastExam.year, PastExam.semester)
            .order_by(PastExam.year.desc())
        )
        result = await conn.execute(query)
        all_exams = [{"id": uuid.UUID(row.id), "year": row.year, "semester": row.semester} for row in result]
        
        # Sort by year desc and slice according to unlocked_count
        # We group by year to count distinct years unlocked
        unique_years = sorted(list(set(e["year"] for e in all_exams)), reverse=True)
        allowed_years = unique_years[:unlocked_count]
        
        return [e for e in all_exams if e["year"] in allowed_years]


    async def get_topics_by_course(self, conn: AsyncConnection, course_id: uuid.UUID) -> list[dict]:
        """Fetch all topics associated with a specific course."""
        query = select(Topic.id, Topic.name).where(Topic.course_id == course_id, Topic.is_active == True)
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name} for row in result]
