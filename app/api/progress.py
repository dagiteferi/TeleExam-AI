from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentTelegramId, ReadDbConn, RedisConn
from app.schemas.progress import ProgressResponse, HistoryResponse, MistakesSummary
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress")


@router.get("/me", response_model=ProgressResponse)
async def get_my_progress(
    conn: ReadDbConn,
    telegram_id: CurrentTelegramId,
    redis: RedisConn,
) -> ProgressResponse:
    """
    Returns the authenticated user's personal progress dashboard.
    
    Security: Data is strictly scoped to the caller's telegram_id.
    No user can access another user's progress data.
    """
    return await ProgressService().get_progress(conn, telegram_id, redis=redis)



@router.get("/history", response_model=HistoryResponse)
async def get_my_history(
    conn: ReadDbConn,
    telegram_id: CurrentTelegramId,
    mode: Literal["all", "exam", "practice"] = "all",
    page: int = Query(0, ge=0),
    page_size: int = Query(10, ge=1, le=50),
    date_from: date | None = Query(None, description="First day to include (Ethiopian local time, UTC+3)"),
    date_to: date | None = Query(None, description="Last day to include (inclusive)"),
) -> HistoryResponse:
    """
    The authenticated user's full results history (newest first), paginated,
    optionally limited to a day range. Scoped to the caller's telegram_id and current department.
    """
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "invalid_range", "message": "date_from must be on or before date_to."}},
        )
    return await ProgressService().get_history(
        conn, telegram_id, mode=mode, page=page, page_size=page_size,
        date_from=date_from, date_to=date_to,
    )


@router.get("/mistakes", response_model=MistakesSummary)
async def get_my_mistakes_summary(
    conn: ReadDbConn,
    telegram_id: CurrentTelegramId,
) -> MistakesSummary:
    """How many questions the user has to review, and whether they can (PRO only)."""
    return await ProgressService().get_mistakes_summary(conn, telegram_id)
