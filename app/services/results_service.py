import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.results import OverallResultsResponse, SessionResultResponse, SessionResultDetail, RecentSessionSummary
from app.models.exam_result import ExamResult
from app.models.user import User
from app.models.user_answer import UserAnswer
from app.models.question import Question
from app.models.topic import Topic

class ResultsService:
    async def get_overall_results(
        self,
        conn: AsyncConnection,
        telegram_id: int,
    ) -> OverallResultsResponse:
        # 1. Get user_id from telegram_id
        user_stmt = select(User.id).where(User.telegram_id == telegram_id)
        user_id = await conn.scalar(user_stmt)
        if not user_id:
            return OverallResultsResponse(
                success=False,
                total_exams_taken=0,
                average_score=0.0,
                weak_topics=[],
                recent_sessions=[],
            )

        # 2. Get stats
        stats_stmt = select(
            func.count(ExamResult.id),
            func.avg(ExamResult.score_percent)
        ).where(ExamResult.user_id == user_id)
        stats = (await conn.execute(stats_stmt)).one()
        
        # 3. Get recent sessions
        recent_stmt = (
            select(ExamResult)
            .where(ExamResult.user_id == user_id)
            .order_by(ExamResult.submitted_at.desc())
            .limit(5)
        )
        recent_res = await conn.execute(recent_stmt)
        recent_sessions = [
            RecentSessionSummary(
                session_id=str(r.id),
                score=int(r.score_percent),
                date=r.submitted_at.isoformat()
            )
            for r in recent_res.scalars()
        ]

        # 4. Get weak topics (dummy for now, but could be implemented similarly)
        return OverallResultsResponse(
            success=True,
            total_exams_taken=stats[0] or 0,
            average_score=float(stats[1] or 0.0),
            weak_topics=["Algebra", "Data Structures"], # TODO: Implement topic weakness analysis
            recent_sessions=recent_sessions,
        )

    async def get_session_results(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        session_id: str,
    ) -> SessionResultResponse:
        # 1. Get user_id from telegram_id
        user_stmt = select(User.id).where(User.telegram_id == telegram_id)
        user_id = await conn.scalar(user_stmt)
        if not user_id:
             return SessionResultResponse(success=False, session_id=session_id, mode="", score=0, total_questions=0, correct_answers=0, incorrect_answers=0)

        # 2. Parse session_id
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            return SessionResultResponse(success=False, session_id=session_id, mode="", score=0, total_questions=0, correct_answers=0, incorrect_answers=0)

        # 3. Get ExamResult
        result_stmt = select(ExamResult).where(ExamResult.id == session_uuid, ExamResult.user_id == user_id)
        result = (await conn.execute(result_stmt)).scalar_one_or_none()
        
        if not result:
            return SessionResultResponse(success=False, session_id=session_id, mode="", score=0, total_questions=0, correct_answers=0, incorrect_answers=0)
            
        # 4. Get Details
        details_stmt = (
            select(
                UserAnswer.question_id,
                UserAnswer.selected_choice,
                UserAnswer.is_correct,
                Question.correct_choice,
                Topic.name.label("topic_name")
            )
            .join(Question, UserAnswer.question_id == Question.id)
            .join(Topic, UserAnswer.topic_id == Topic.id)
            .where(UserAnswer.exam_result_id == session_uuid)
            .order_by(UserAnswer.answered_at.asc())
        )
        details_res = await conn.execute(details_stmt)
        
        questions_details = [
            SessionResultDetail(
                question_id=row.question_id,
                user_answer=row.selected_choice,
                correct_answer=row.correct_choice,
                is_correct=row.is_correct,
                topic=row.topic_name
            )
            for row in details_res
        ]
        
        return SessionResultResponse(
            success=True,
            session_id=session_id,
            mode=result.mode,
            score=int(result.score_percent),
            total_questions=result.question_count,
            correct_answers=result.correct_count,
            incorrect_answers=result.wrong_count,
            questions_details=questions_details
        )
