from __future__ import annotations
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import CurrentTelegramId, DbConn
from app.schemas.ai import ExplainRequest, ExplainResponse, ChatRequest, ChatResponse, StudyPlanRequest, StudyPlanResponse
from app.services.ai_service import AiService

router = APIRouter(prefix="/ai")


@router.post("/explain", response_model=ExplainResponse)
async def explain_question(
    request: ExplainRequest,
    _current_telegram_id: int = CurrentTelegramId,
    conn: AsyncConnection = DbConn,
) -> ExplainResponse:
    return await AiService().explain_question(
        conn, request.telegram_id, request.question_id, request.user_answer
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    _current_telegram_id: int = CurrentTelegramId,
    conn: AsyncConnection = DbConn,
) -> ChatResponse:
    return await AiService().chat(conn, request.telegram_id, request.message)


@router.post("/study-plan", response_model=StudyPlanResponse)
async def create_study_plan(
    request: StudyPlanRequest,
    _current_telegram_id: int = CurrentTelegramId,
    conn: AsyncConnection = DbConn,
) -> StudyPlanResponse:
    return await AiService().generate_study_plan(conn, request.telegram_id)
