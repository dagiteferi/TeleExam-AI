from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from redis.asyncio import Redis

from app.api.deps import get_current_telegram_id, get_db_conn, get_redis
from app.schemas.sessions import (
    SessionMode,
    StartSessionRequest,
    StartSessionResponse,
    GetQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    NextResponse,
    SubmitSessionResponse,
)
from app.services.session_service import SessionService
from app.models.user import User # Needed to get user_id from telegram_id
from sqlalchemy import select

router = APIRouter(prefix="/sessions")


@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    request_data: StartSessionRequest,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> StartSessionResponse:
    # Get user_id from telegram_id
    user = await conn.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "User not found."}},
        )

    return await SessionService(redis).start_session(
        conn, telegram_id, user.id, request_data
    )


@router.get("/{session_id}", response_model=dict) # TODO: Define a proper schema for session metadata
async def get_session_metadata(
    session_id: uuid.UUID,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    # This endpoint should return minimal session metadata, not full question list
    # For now, just return a placeholder
    return {"session_id": session_id, "status": "in_progress", "message": "Session metadata endpoint not fully implemented yet."}


@router.get("/{session_id}/question", response_model=GetQuestionResponse)
async def get_question(
    session_id: uuid.UUID,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> GetQuestionResponse:
    # This will be implemented in SessionService
    return await SessionService(redis).get_question(conn, telegram_id, session_id)


@router.post("/{session_id}/answer", response_model=SubmitAnswerResponse)
async def submit_answer(
    session_id: uuid.UUID,
    request_data: SubmitAnswerRequest,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SubmitAnswerResponse:
    # This will be implemented in SessionService
    return await SessionService(redis).submit_answer(conn, telegram_id, session_id, request_data)


@router.post("/{session_id}/next", response_model=NextResponse)
async def next_question(
    session_id: uuid.UUID,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> NextResponse:
    # This will be implemented in SessionService
    return await SessionService(redis).next_question(conn, telegram_id, session_id)


@router.post("/{session_id}/submit", response_model=SubmitSessionResponse)
async def submit_session(
    session_id: uuid.UUID,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SubmitSessionResponse:
    # This will be implemented in SessionService
    return await SessionService(redis).submit_session(conn, telegram_id, session_id)