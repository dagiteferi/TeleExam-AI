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
from app.services.access_service import AccessService
from app.services.invitation_service import InvitationService


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

    async def get_available_courses(self, conn: AsyncConnection, telegram_id: int | None = None, department_id: uuid.UUID | None = None) -> list[dict]:
        """Fetch unique course names and their IDs, optionally filtered by department. 1/4 free, rest locked based on invites."""
        query = select(Course.id, Course.name, Course.department_id).where(Course.is_active == True)
        if department_id:
            query = query.where(Course.department_id == department_id)
        
        query = query.distinct().order_by(Course.name.asc())
        result = await conn.execute(query)
        courses = [{"id": row.id, "name": row.name, "department_id": row.department_id} for row in result]

        access = await AccessService.get_by_telegram_id(conn, telegram_id)
        if department_id and access and not access.can_use_department(department_id):
            return []

        invite_config = await InvitationService.get_config(conn)
        invite_count = access.invite_count if access else 0
        fully_unlocked = bool(access and access.fully_unlocks(department_id))

        total_courses = len(courses)
        unlocked_count = invite_config.calculate_unlocked_courses_count(
            invite_count=invite_count,
            total_courses=total_courses,
            fully_unlocked=fully_unlocked,
        )

        unlock_threshold = min(invite_config.invites_to_unlock_all, invite_config.invites_to_unlock_all_courses)

        for i, c in enumerate(courses):
            c["is_locked"] = i >= unlocked_count
            if c["is_locked"]:
                c["required_invites"] = unlock_threshold
            else:
                c["required_invites"] = 0

        return courses

    async def get_available_departments(self, conn: AsyncConnection) -> list[dict]:
        """Fetch all active departments."""
        query = select(Department.id, Department.name).where(Department.is_active == True)
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name} for row in result]

    async def get_exams_by_department(self, conn: AsyncConnection, department_id: uuid.UUID, telegram_id: int | None = None) -> list[dict]:
        """List available years and semesters for a specific department (deduplicated)."""
        access = await AccessService.get_by_telegram_id(conn, telegram_id)
        if access and not access.can_use_department(department_id):
            return []

        invite_config = await InvitationService.get_config(conn)
        invite_count = access.invite_count if access else 0
        fully_unlocked = bool(access and access.fully_unlocks(department_id))

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

        # The oldest exams are available for free based on invite_config.free_years.
        unique_years = sorted(list(set(e["year"] for e in all_exams)), reverse=False) # Ascending: 2015, 2016, 2017
        allowed_years = invite_config.calculate_allowed_years(
            all_years_sorted_asc=unique_years,
            invite_count=invite_count,
            fully_unlocked=fully_unlocked,
        )

        # Add lock status to each exam
        for e in all_exams:
            e["is_locked"] = e["year"] not in allowed_years
            if e["is_locked"]:
                e["required_invites"] = invite_config.calculate_required_invites_for_year(
                    year=e["year"],
                    all_years_sorted_asc=unique_years,
                )
            else:
                e["required_invites"] = 0

        return all_exams


    async def get_topics_by_course(self, conn: AsyncConnection, course_id: uuid.UUID) -> list[dict]:
        """Fetch all topics associated with a specific course."""
        query = select(Topic.id, Topic.name).where(Topic.course_id == course_id, Topic.is_active == True)
        result = await conn.execute(query)
        return [{"id": row.id, "name": row.name} for row in result]
