from __future__ import annotations

import json

from sqlalchemy import select, func, String, true
from sqlalchemy.ext.asyncio import AsyncConnection
from redis.asyncio import Redis

from app.models.user import User
from app.models.exam_result import ExamResult
from app.models.user_topic_error import UserTopicError
from app.models.topic import Topic
from app.models.course import Course
from app.models.question import Question
from app.models.user_answer import UserAnswer
from app.models.department import Department
from app.services.access_service import AccessService
from app.schemas.progress import ProgressResponse, CourseProgress, WeakTopic, TopExamScore, ActiveSessionInfo, RecentSession
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

        # Dual-degree students see progress for the department they are studying now.
        access = await AccessService.get_by_user_id(conn, user_id)
        dept_id = access.effective_department_id if access else None
        in_dept = (Course.department_id == dept_id) if dept_id else true()
        department_name = await conn.scalar(select(Department.name).where(Department.id == dept_id)) if dept_id else None

        # 2. Overall aggregates (exam mode only for "exams taken").
        # "Answered" is correct + wrong: question_count also includes questions the
        # student skipped, which would inflate the total and deflate accuracy.
        overall_row = await conn.execute(
            select(
                func.count(ExamResult.id).filter(ExamResult.mode == "exam").label("exam_count"),
                func.count(ExamResult.id).filter(ExamResult.mode == "practice").label("practice_count"),
                func.sum(ExamResult.correct_count).label("total_correct"),
                func.sum(ExamResult.wrong_count).label("total_wrong"),
            )
            .join(Course, ExamResult.course_id == Course.id)
            .where(ExamResult.user_id == user_id, in_dept)
        )
        overall = overall_row.fetchone()

        total_correct = int(overall.total_correct or 0)
        total_wrong = int(overall.total_wrong or 0)
        total_answered = total_correct + total_wrong
        overall_accuracy = round((total_correct / total_answered * 100), 1) if total_answered > 0 else 0.0

        # 3. Per-course breakdown from the individual answers, so a past exam that
        # spans several courses is split across them correctly.
        answered_expr = func.count(UserAnswer.id)
        correct_expr = func.count(UserAnswer.id).filter(UserAnswer.is_correct.is_(True))
        course_rows = await conn.execute(
            select(
                Course.name.label("course_name"),
                answered_expr.label("total"),
                correct_expr.label("correct"),
            )
            .join(Question, UserAnswer.question_id == Question.id)
            .join(Course, Question.course_id == Course.id)
            .where(UserAnswer.user_id == user_id, in_dept)
            .group_by(Course.name)
            .order_by(answered_expr.desc())
        )
        course_breakdown = []
        for row in course_rows.fetchall():
            total = int(row.total or 0)
            correct = int(row.correct or 0)
            course_breakdown.append(CourseProgress(
                course_name=row.course_name,
                total_answered=total,
                correct=correct,
                wrong=total - correct,
                accuracy_percent=round((correct / total * 100), 1) if total > 0 else 0.0,
            ))

        # 4. Weak topics (top 5 by error count)
        topic_rows = await conn.execute(
            select(Topic.name, UserTopicError.error_count)
            .join(Topic, UserTopicError.topic_id == Topic.id)
            .join(Course, Topic.course_id == Course.id)
            .where(UserTopicError.user_id == user_id, in_dept)
            .order_by(UserTopicError.error_count.desc())
            .limit(5)
        )
        weak_topics = [
            WeakTopic(topic_name=row.name, error_count=row.error_count)
            for row in topic_rows.fetchall()
        ]

        # 5-6, 8. Recent scores, top results and history all come from the user's
        # results, newest first. The title saved with the result (e.g. "2016 First
        # Exam") is preferred; older results fall back to their course name.
        result_rows = (await conn.execute(
            select(
                ExamResult.mode,
                ExamResult.score_percent,
                ExamResult.question_count,
                ExamResult.correct_count,
                ExamResult.wrong_count,
                ExamResult.submitted_at,
                ExamResult.metadata_,
                Course.name.label("course_name"),
            )
            .outerjoin(Course, ExamResult.course_id == Course.id)
            .where(ExamResult.user_id == user_id, in_dept)
            .order_by(ExamResult.submitted_at.desc())
            .limit(200)
        )).fetchall()

        def _title(row) -> str:
            return (row.metadata_ or {}).get("title") or row.course_name or "Exam"

        exam_rows = [row for row in result_rows if row.mode == "exam"]

        # Last 5 exam scores, oldest -> newest for the trend display
        recent_scores = [float(row.score_percent) for row in reversed(exam_rows[:5])]

        best_by_title: dict[str, TopExamScore] = {}
        for row in exam_rows:
            title = _title(row)
            score = float(row.score_percent or 0.0)
            if title not in best_by_title or score > best_by_title[title].top_score_percent:
                best_by_title[title] = TopExamScore(
                    title=title,
                    top_score_percent=score,
                    total_questions=int(row.question_count or 0),
                )
        top_exam_scores = sorted(
            best_by_title.values(), key=lambda t: t.top_score_percent, reverse=True
        )[:5]

        recent_sessions = [
            RecentSession(
                mode=row.mode,
                title=_title(row),
                score_percent=float(row.score_percent or 0.0),
                question_count=int(row.question_count or 0),
                answered_count=int(row.correct_count or 0) + int(row.wrong_count or 0),
                submitted_at=row.submitted_at,
            )
            for row in result_rows[:5]
        ]

        # 7. Active / In-Progress Session details from Redis
        active_info = None
        if redis:
            for m in ("exam", "practice", "quiz"):
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
                            title = parsed.get("title") or ("Past Exam" if m == "exam" else "Practice Session")
                            active_info = ActiveSessionInfo(
                                mode=m,
                                title=title,
                                current_question_index=min(curr_idx, tot_q) if tot_q else curr_idx,
                                total_questions=tot_q,
                                answered_count=len(json.loads(parsed.get("answers") or "{}")),
                            )
                            break

        return ProgressResponse(
            department_name=department_name,
            total_exams_taken=int(overall.exam_count or 0),
            total_practice_sessions=int(overall.practice_count or 0),
            overall_accuracy_percent=overall_accuracy,
            total_questions_answered=total_answered,
            total_correct=total_correct,
            total_wrong=total_wrong,
            course_breakdown=course_breakdown,
            weak_topics=weak_topics,
            recent_exam_scores=recent_scores,
            top_exam_scores=top_exam_scores,
            active_session_info=active_info,
            recent_sessions=recent_sessions,
        )

