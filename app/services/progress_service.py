from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.user import User
from app.models.exam_result import ExamResult
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic
from app.models.course import Course
from app.schemas.progress import ProgressResponse, CourseProgress, WeakTopic


class ProgressService:
    """
    Returns private progress data for a single authenticated user.
    All queries are scoped strictly to the user's own ID — no cross-user leakage.
    """

    async def get_progress(
        self,
        conn: AsyncConnection,
        telegram_id: int,
    ) -> ProgressResponse:
        # 1. Resolve telegram_id -> user_id
        user_id = await conn.scalar(
            select(User.id).where(User.telegram_id == telegram_id)
        )
        if not user_id:
            # Return empty progress for brand new users
            return ProgressResponse(
                total_exams_taken=0,
                total_practice_sessions=0,
                overall_accuracy_percent=0.0,
                total_questions_answered=0,
                total_correct=0,
                total_wrong=0,
                course_breakdown=[],
                weak_topics=[],
                recent_exam_scores=[],
            )

        # 2. Overall aggregates (exam mode only for "exams taken")
        overall_row = await conn.execute(
            select(
                func.count(ExamResult.id).filter(ExamResult.mode == "exam").label("exam_count"),
                func.count(ExamResult.id).filter(ExamResult.mode == "practice").label("practice_count"),
                func.sum(ExamResult.correct_count).label("total_correct"),
                func.sum(ExamResult.wrong_count).label("total_wrong"),
                func.sum(ExamResult.question_count).label("total_questions"),
            ).where(ExamResult.user_id == user_id)
        )
        overall = overall_row.fetchone()

        total_correct = int(overall.total_correct or 0)
        total_wrong = int(overall.total_wrong or 0)
        total_questions = int(overall.total_questions or 0)
        overall_accuracy = round((total_correct / total_questions * 100), 1) if total_questions > 0 else 0.0

        # 3. Per-course breakdown (only exam mode sessions for accuracy)
        course_rows = await conn.execute(
            select(
                Course.name.label("course_name"),
                func.sum(ExamResult.correct_count).label("correct"),
                func.sum(ExamResult.wrong_count).label("wrong"),
                func.sum(ExamResult.question_count).label("total"),
            )
            .join(Course, ExamResult.course_id == Course.id)
            .where(ExamResult.user_id == user_id)
            .group_by(Course.name)
            .order_by(func.sum(ExamResult.question_count).desc())
        )
        course_breakdown = []
        for row in course_rows.fetchall():
            total = int(row.total or 0)
            correct = int(row.correct or 0)
            wrong = int(row.wrong or 0)
            accuracy = round((correct / total * 100), 1) if total > 0 else 0.0
            course_breakdown.append(CourseProgress(
                course_name=row.course_name,
                total_answered=total,
                correct=correct,
                wrong=wrong,
                accuracy_percent=accuracy,
            ))

        # 4. Weak topics (top 5 by error count)
        topic_rows = await conn.execute(
            select(Topic.name, UserTopicError.error_count)
            .join(Topic, UserTopicError.topic_id == Topic.id)
            .where(UserTopicError.user_id == user_id)
            .order_by(UserTopicError.error_count.desc())
            .limit(5)
        )
        weak_topics = [
            WeakTopic(topic_name=row.name, error_count=row.error_count)
            for row in topic_rows.fetchall()
        ]

        # 5. Last 5 exam scores (chronological for trend display)
        score_rows = await conn.execute(
            select(ExamResult.score_percent)
            .where(ExamResult.user_id == user_id, ExamResult.mode == "exam")
            .order_by(ExamResult.submitted_at.asc())
            .limit(5)
        )
        recent_scores = [float(row.score_percent) for row in score_rows.fetchall()]

        return ProgressResponse(
            total_exams_taken=int(overall.exam_count or 0),
            total_practice_sessions=int(overall.practice_count or 0),
            overall_accuracy_percent=overall_accuracy,
            total_questions_answered=total_questions,
            total_correct=total_correct,
            total_wrong=total_wrong,
            course_breakdown=course_breakdown,
            weak_topics=weak_topics,
            recent_exam_scores=recent_scores,
        )
