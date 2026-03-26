from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.models.exam import AnswerRequest, AnswerResponse, Mode, NextQuestionResponse, StartExamResponse
from app.services.exam_service import ExamService

router = APIRouter(prefix="/exam")


@router.get("/start", response_model=StartExamResponse)
async def start_exam(
    mode: Mode = Query(...),
    course_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> StartExamResponse:
    try:
        data = await ExamService().start_session(
            conn,
            telegram_id=telegram_id,
            mode=mode,
            course_id=course_id,
            topic_id=topic_id,
        )
        return StartExamResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/next/{session_id}", response_model=NextQuestionResponse)
async def get_next_question(
    session_id: str,
    _: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> NextQuestionResponse:
    try:
        data = await ExamService().next_question(conn, session_id=session_id)
        return NextQuestionResponse(**data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    payload: AnswerRequest,
    _: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> AnswerResponse:
    try:
        data = await ExamService().submit_answer(
            conn,
            session_id=payload.session_id,
            question_id=payload.question_id,
            answer=payload.answer,
        )
        return AnswerResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

