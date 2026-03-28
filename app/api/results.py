from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.models.results import OverallResultsResponse, SessionResultResponse
from app.services.results_service import ResultsService

router = APIRouter(prefix="/results")

@router.get("/{telegram_id}", response_model=OverallResultsResponse)
async def get_overall_results(
    telegram_id: int,
    _current_telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> OverallResultsResponse:
    return await ResultsService().get_overall_results(conn, telegram_id)

@router.get("/session/{session_id}", response_model=SessionResultResponse)
async def get_session_results(
    session_id: str,
    telegram_id: Annotated[int, Depends(get_current_telegram_id)],
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> SessionResultResponse:
    return await ResultsService().get_session_results(conn, telegram_id, session_id)
