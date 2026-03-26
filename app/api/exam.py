from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import CurrentTelegramId, DbConn
from app.models.exam import Mode, StartExamResponse, NextQuestionResponse, AnswerRequest, AnswerResponse
from app.services.exam_service import ExamService

router = APIRouter(prefix="/exam")


@router.get("/start", response_model=StartExamResponse)
async def start_exam(
    mode: Mode,
    course_id: int | None = None,
    topic_id: int | None = None,
    telegram_id: int = CurrentTelegramId,
    conn: AsyncConnection = DbConn,
) -> StartExamResponse:
    if mode == "exam" and course_id is None:
        raise HTTPException(status_code=400, detail="course_id is required for exam mode")
    if mode in ["practice", "quiz"] and topic_id is None:
        raise HTTPException(status_code=400, detail="topic_id is required for practice/quiz mode")
        
    return await ExamService().start_session(
        conn, telegram_id, mode, course_id=course_id, topic_id=topic_id
    )


@router.get("/next/{session_id}", response_model=NextQuestionResponse)
async def get_next_question(
    session_id: str,
    telegram_id: int = CurrentTelegramId,
    conn: AsyncConnection = DbConn,
) -> NextQuestionResponse:
    return await ExamService().get_next_question(conn, telegram_id, session_id)


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    request: AnswerRequest,
    telegram_id: int = CurrentTelegramId,
    conn: AsyncConnection = DbConn,
) -> AnswerResponse:
    return await ExamService().submit_answer(
        conn, telegram_id, request.session_id, request.question_id, request.answer
    )
