from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text, func, select, Integer

from app.admin.deps import require_permission
from app.db.postgres import db_conn
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.models.exam_result import ExamResult
from app.models.question import Question
from app.models.user_answer import UserAnswer
from app.schemas.admin import DAUResponse, ReferralStatsResponse, ExamStatsResponse, QuestionStatsResponse

async def get_admin_db():
    async with db_conn(telegram_id=None) as conn:
        yield conn

router = APIRouter(prefix="/stats", dependencies=[Depends(require_permission("view_stats"))])

@router.get("/dau", response_model=DAUResponse)
async def get_daily_active_users(
    start_date: date,
    end_date: date,
    conn: AsyncConnection = Depends(get_admin_db),
) -> DAUResponse:
    query = text("""
        SELECT date_trunc('day', created_at) AS day, COUNT(DISTINCT user_id) AS dau
        FROM activity_logs
        WHERE created_at >= :start_date AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY 1
        ORDER BY 1
    """)
    result = await conn.execute(query, {"start_date": start_date, "end_date": end_date})
    dau_data = [{"day": row.day.date(), "dau": row.dau} for row in result]
    return DAUResponse(data=dau_data)

@router.get("/referrals", response_model=ReferralStatsResponse)
async def get_referral_stats(
    conn: AsyncConnection = Depends(get_admin_db),
    limit: int = 10,
    offset: int = 0,
) -> ReferralStatsResponse:
    query = select(User.id, User.telegram_id, User.telegram_username, User.invite_count).order_by(User.invite_count.desc()).limit(limit).offset(offset)
    result = await conn.execute(query)
    top_inviters = [{"user_id": row.id, "telegram_id": row.telegram_id, "telegram_username": row.telegram_username, "invite_count": row.invite_count} for row in result]
    return ReferralStatsResponse(top_inviters=top_inviters)

@router.get("/exams", response_model=ExamStatsResponse)
async def get_exam_stats(
    conn: AsyncConnection = Depends(get_admin_db),
    start_date: date | None = None,
    end_date: date | None = None,
) -> ExamStatsResponse:
    query = select(
        func.count(ExamResult.id).label("total_exams"),
        func.count(func.distinct(ExamResult.user_id)).label("total_users"),
        func.avg(ExamResult.score_percent).label("average_score"),
    ).where(ExamResult.mode == "exam")

    if start_date:
        query = query.where(ExamResult.submitted_at >= start_date)
    if end_date:
        query = query.where(ExamResult.submitted_at < end_date + timedelta(days=1))

    result = await conn.execute(query)
    stats = result.first()

    return ExamStatsResponse(
        total_exams=stats.total_exams if stats else 0,
        total_users=stats.total_users if stats else 0,
        average_score=round(float(stats.average_score), 2) if stats and stats.average_score else 0.0,
    )

@router.get("/questions", response_model=list[QuestionStatsResponse])
async def get_question_stats(
    conn: AsyncConnection = Depends(get_admin_db),
    course_id: UUID | None = None,
    topic_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[QuestionStatsResponse]:
    query = select(
        Question.id.label("question_id"),
        func.count(UserAnswer.id).label("attempt_count"),
        func.sum(func.cast(UserAnswer.is_correct, Integer)).label("correct_count"),
    ).join(UserAnswer, Question.id == UserAnswer.question_id).group_by(Question.id).limit(limit).offset(offset)
    
    if course_id:
        query = query.where(Question.course_id == course_id)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)

    result = await conn.execute(query)
    stats = []
    for row in result:
        correct = row.correct_count or 0
        total = row.attempt_count or 1
        stats.append(QuestionStatsResponse(
            question_id=row.question_id,
            attempt_count=total,
            correct_rate=round(correct / total, 2)
        ))
    return stats
