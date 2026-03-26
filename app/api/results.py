from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.models.results import ResultsSummaryResponse, SessionDetailsResponse
from app.services.results_service import ResultsService

router = APIRouter(prefix="/results")


@router.get("/{telegram_id}", response_model=ResultsSummaryResponse)
async def results_summary(
    telegram_id: int,
    current_tid: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> ResultsSummaryResponse:
    if telegram_id != current_tid:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = await ResultsService().get_summary(conn, telegram_id=telegram_id)
    return ResultsSummaryResponse(**data)


@router.get("/session/{session_id}", response_model=SessionDetailsResponse)
async def session_details(
    session_id: str,
    _: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn),
) -> SessionDetailsResponse:
    try:
        data = await ResultsService().get_session_details(conn, session_id=session_id)
        return SessionDetailsResponse(**data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

