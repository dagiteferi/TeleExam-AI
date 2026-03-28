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
    conn: DbConn,
    _current_telegram_id: CurrentTelegramId,
) -> ExplainResponse:
    return await AiService().explain_question(
        conn, _current_telegram_id, request.question_id, request.user_answer
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    conn: DbConn,
    _current_telegram_id: CurrentTelegramId,
) -> ChatResponse:
    return await AiService().chat(conn, _current_telegram_id, request.message)


@router.post("/study-plan", response_model=StudyPlanResponse)
async def create_study_plan(
    request: StudyPlanRequest,
    conn: DbConn,
    _current_telegram_id: CurrentTelegramId,
) -> StudyPlanResponse:
    return await AiService().generate_study_plan(conn, _current_telegram_id)
