from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.models.ai import ChatRequest, ChatResponse, ExplainRequest, ExplainResponse
from app.services.ai_service import AiService
from app.services.rate_limit_service import RateLimitExceededError, RateLimitService

router = APIRouter(prefix="/ai")

_rate_limiter = RateLimitService()


def _enforce_rate_limit(telegram_id: int = Depends(get_current_telegram_id)) -> int:
    try:
        _rate_limiter.check(telegram_id)
        return telegram_id
    except RateLimitExceededError as e:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(e.retry_after_seconds)},
        ) from e


@router.post("/explain", response_model=ExplainResponse, dependencies=[Depends(_enforce_rate_limit)])
async def explain(
    payload: ExplainRequest,
    conn: AsyncConnection = Depends(get_db_conn),
) -> ExplainResponse:
    try:
        data = await AiService().explain(
            conn,
            question_id=payload.question_id,
            user_answer=payload.user_answer,
        )
        return ExplainResponse(**data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(_enforce_rate_limit)])
async def chat(payload: ChatRequest) -> ChatResponse:
    data = await AiService().chat(message=payload.message)
    return ChatResponse(**data)

