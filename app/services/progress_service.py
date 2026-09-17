from __future__ import annotations

from sqlalchemy import select, func, String
from sqlalchemy.ext.asyncio import AsyncConnection
from redis.asyncio import Redis

from app.models.user import User
from app.models.exam_result import ExamResult
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic
from app.models.course import Course
from app.models.past_exam import PastExam
from app.schemas.progress import ProgressResponse, CourseProgress, WeakTopic, TopExamScore, ActiveSessionInfo
from app.db.redis import get_active_session_key, get_session_key


class ProgressService:
    """
    Returns private progress data for a single authenticated user.
    All queries are scoped strictly to the user's own ID — no cross-user leakage.
    """

    async def get_progress(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        redis: Redis | None = None,
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
                top_exam_scores=[],
                active_session_info=None,
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

        # 6. Top Exam Scores
        top_rows = await conn.execute(
            select(
                Course.name.label("title"),
                func.max(ExamResult.score_percent).label("top_score"),
                func.max(ExamResult.question_count).label("total_qs"),
            )
            .join(Course, ExamResult.course_id == Course.id)
            .where(ExamResult.user_id == user_id, ExamResult.mode == "exam")
            .group_by(Course.name)
            .order_by(func.max(ExamResult.score_percent).desc())
            .limit(5)
        )
        top_exam_scores = [
            TopExamScore(
                title=row.title or "Exam",
                top_score_percent=float(row.top_score or 0.0),
                total_questions=int(row.total_qs or 0),
            )
            for row in top_rows.fetchall() if row.title
        ]


        # 7. Active / In-Progress Session details from Redis
        active_info = None
        if redis:
            for m in ("exam", "practice"):
                active_key = get_active_session_key(user_id, m)
                active_sid = await redis.get(active_key)
                if active_sid:
                    sid_str = active_sid.decode() if isinstance(active_sid, bytes) else str(active_sid)
                    sess_data = await redis.hgetall(get_session_key(sid_str))
                    if sess_data:
                        # Convert bytes if needed
                        parsed = {
                            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                            for k, v in sess_data.items()
                        }
                        if parsed.get("status") == "in_progress":
                            curr_idx = int(parsed.get("current_index", 0)) + 1
                            tot_q = int(parsed.get("total_questions", 0))
                            title = parsed.get("title") or parsed.get("course_name") or ("Past Exam" if m == "exam" else "Practice Session")
                            active_info = ActiveSessionInfo(
                                mode=m,
                                title=title,
                                current_question_index=curr_idx,
                                total_questions=tot_q,
                            )
                            break

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
            top_exam_scores=top_exam_scores,
            active_session_info=active_info,
        )

