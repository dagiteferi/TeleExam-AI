from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func, Float, true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.course import Course
from app.models.topic import Topic
from app.models.user_answer import UserAnswer
from app.models.user_topic_error import UserTopicError

# Weak-topic rules: a topic is judged on the student's most recent answers only,
# so it stops being "weak" once they start getting it right.
RECENT_ANSWERS_PER_TOPIC = 20
MIN_ATTEMPTS = 3            # too few answers says nothing about a topic
MIN_ERROR_RATE = 0.3        # below 30% wrong the topic is not flagged
RECENT_ANSWERS_PER_COURSE = 30  # course fallback: a course covers several topics


class AnalyticsService:
    async def record_user_topic_error(
        self, conn: AsyncConnection, user_id: UUID, topic_id: UUID
    ) -> None:
        await self.record_user_topic_errors(conn, user_id, {topic_id: 1})

    async def record_user_topic_errors(
        self, conn: AsyncConnection, user_id: UUID, error_counts: dict[UUID, int]
    ) -> None:
        """Lifetime mistake counter per topic (kept for admin/history, not used for ranking)."""
        if not error_counts:
            return
        stmt = pg_insert(UserTopicError).values([
            {"user_id": user_id, "topic_id": topic_id, "error_count": count}
            for topic_id, count in error_counts.items()
        ])
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "topic_id"],
            set_={"error_count": UserTopicError.error_count + stmt.excluded.error_count}
        )
        await conn.execute(stmt)

    @staticmethod
    def _open_mistakes_query(user_id: UUID, department_id: UUID | None, question_id: UUID | None = None):
        """
        Questions whose most recent answer by this student was wrong.
        Answering one correctly (e.g. in Review My Mistakes) removes it from the list.
        question_id limits it to that one question (is it still an open mistake?).
        """
        from app.models.question import Question

        latest = (
            select(
                UserAnswer.question_id,
                UserAnswer.is_correct,
                UserAnswer.selected_choice,
                UserAnswer.answered_at,
                func.row_number().over(
                    partition_by=UserAnswer.question_id,
                    order_by=UserAnswer.answered_at.desc(),
                ).label("rn"),
            )
            .where(
                UserAnswer.user_id == user_id,
                (UserAnswer.question_id == question_id) if question_id else true(),
            )
            .subquery()
        )
        in_dept = (Course.department_id == department_id) if department_id else true()
        return (
            select(latest.c.question_id)
            .join(Question, Question.id == latest.c.question_id)
            .join(Course, Question.course_id == Course.id)
            .where(
                latest.c.rn == 1,
                latest.c.is_correct.is_(False),
                Question.is_active.is_(True),
                in_dept,
            )
            .order_by(latest.c.answered_at.desc(), latest.c.question_id)
        ), latest

    async def count_open_mistakes(
        self, conn: AsyncConnection, user_id: UUID, department_id: UUID | None = None
    ) -> int:
        query, _ = self._open_mistakes_query(user_id, department_id)
        sub = query.order_by(None).subquery()
        return int(await conn.scalar(select(func.count()).select_from(sub)) or 0)

    async def get_open_mistake_ids(
        self,
        conn: AsyncConnection,
        user_id: UUID,
        department_id: UUID | None = None,
        limit: int = 20,
        question_id: UUID | None = None,
    ) -> list[UUID]:
        """Most recent mistakes first, up to `limit` (or just `question_id` if it is still open)."""
        query, _ = self._open_mistakes_query(user_id, department_id, question_id)
        rows = await conn.scalars(query.limit(limit))
        return list(rows.all())

    async def get_open_mistakes_page(
        self, conn: AsyncConnection, user_id: UUID, department_id: UUID | None, offset: int, limit: int
    ) -> list:
        """
        A page of open mistakes (most recent first): question text, the student's
        wrong answer and the course name. The correct answer is not selected.
        """
        from app.models.question import Question

        query, latest = self._open_mistakes_query(user_id, department_id)
        query = query.add_columns(
            latest.c.selected_choice,
            latest.c.answered_at,
            Question.prompt,
            Course.name.label("course_name"),
        )
        return list((await conn.execute(query.offset(offset).limit(limit))).fetchall())

    async def count_open_mistakes_by_course(
        self, conn: AsyncConnection, user_id: UUID, department_id: UUID | None
    ) -> list[tuple[str, int]]:
        """[(course name, open mistakes)], most mistakes first — the summary at the top of the list."""
        query, _ = self._open_mistakes_query(user_id, department_id)
        sub = query.order_by(None).add_columns(Course.name.label("course_name")).subquery()
        rows = await conn.execute(
            select(sub.c.course_name, func.count().label("n"))
            .group_by(sub.c.course_name)
            .order_by(func.count().desc(), sub.c.course_name)
        )
        return [(row.course_name, int(row.n)) for row in rows.fetchall()]

    async def get_weak_topics(
        self,
        conn: AsyncConnection,
        user_id: UUID,
        department_id: UUID | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Topics the student is currently weak in, worst first.

        Each topic is scored on its last RECENT_ANSWERS_PER_TOPIC answers as
        wrong / attempted, so improvement lowers the rate and the topic drops off.
        Returns dicts with topic_name, wrong, attempted and error_rate_percent.
        """
        recent = (
            select(
                UserAnswer.topic_id,
                UserAnswer.is_correct,
                func.row_number().over(
                    partition_by=UserAnswer.topic_id,
                    order_by=UserAnswer.answered_at.desc(),
                ).label("rn"),
            )
            .where(UserAnswer.user_id == user_id)
            .subquery()
        )

        attempted = func.count()
        wrong = func.count().filter(recent.c.is_correct.is_(False))
        error_rate = wrong.cast(Float) / attempted.cast(Float)
        in_dept = (Course.department_id == department_id) if department_id else true()

        rows = await conn.execute(
            select(
                Topic.name.label("topic_name"),
                attempted.label("attempted"),
                wrong.label("wrong"),
            )
            .select_from(recent)
            .join(Topic, Topic.id == recent.c.topic_id)
            .join(Course, Topic.course_id == Course.id)
            .where(recent.c.rn <= RECENT_ANSWERS_PER_TOPIC, in_dept)
            .group_by(Topic.id, Topic.name)
            .having(attempted >= MIN_ATTEMPTS, error_rate >= MIN_ERROR_RATE)
            .order_by(error_rate.desc(), wrong.desc())
            .limit(limit)
        )
        return [
            {
                "topic_name": row.topic_name,
                "wrong": int(row.wrong),
                "attempted": int(row.attempted),
                "error_rate_percent": round(row.wrong / row.attempted * 100, 1),
            }
            for row in rows.fetchall()
        ]

    async def get_weak_courses(
        self,
        conn: AsyncConnection,
        user_id: UUID,
        department_id: UUID | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Same rules as get_weak_topics, but per course. Used when the student's answers
        are spread too thinly for any single topic to reach MIN_ATTEMPTS (common early
        on, because topics are small). Returns the same dict shape, with the course
        name in "topic_name".
        """
        recent = (
            select(
                Topic.course_id,
                UserAnswer.is_correct,
                func.row_number().over(
                    partition_by=Topic.course_id,
                    order_by=UserAnswer.answered_at.desc(),
                ).label("rn"),
            )
            .join(Topic, Topic.id == UserAnswer.topic_id)
            .where(UserAnswer.user_id == user_id)
            .subquery()
        )

        attempted = func.count()
        wrong = func.count().filter(recent.c.is_correct.is_(False))
        error_rate = wrong.cast(Float) / attempted.cast(Float)
        in_dept = (Course.department_id == department_id) if department_id else true()

        rows = await conn.execute(
            select(
                Course.name.label("course_name"),
                attempted.label("attempted"),
                wrong.label("wrong"),
            )
            .select_from(recent)
            .join(Course, Course.id == recent.c.course_id)
            .where(recent.c.rn <= RECENT_ANSWERS_PER_COURSE, in_dept)
            .group_by(Course.id, Course.name)
            .having(attempted >= MIN_ATTEMPTS, error_rate >= MIN_ERROR_RATE)
            .order_by(error_rate.desc(), wrong.desc())
            .limit(limit)
        )
        return [
            {
                "topic_name": row.course_name,
                "wrong": int(row.wrong),
                "attempted": int(row.attempted),
                "error_rate_percent": round(row.wrong / row.attempted * 100, 1),
            }
            for row in rows.fetchall()
        ]

    async def count_answers(
        self, conn: AsyncConnection, user_id: UUID, department_id: UUID | None = None
    ) -> int:
        """How many questions the student has answered (in the department, if given)."""
        in_dept = (Course.department_id == department_id) if department_id else true()
        return int(await conn.scalar(
            select(func.count())
            .select_from(UserAnswer)
            .join(Topic, Topic.id == UserAnswer.topic_id)
            .join(Course, Course.id == Topic.course_id)
            .where(UserAnswer.user_id == user_id, in_dept)
        ) or 0)
