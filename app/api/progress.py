from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentTelegramId, DbConn
from app.schemas.progress import ProgressResponse
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress")


@router.get("/me", response_model=ProgressResponse)
async def get_my_progress(
    conn: DbConn,
    telegram_id: CurrentTelegramId,
) -> ProgressResponse:
    """
    Returns the authenticated user's personal progress dashboard.
    
    Security: Data is strictly scoped to the caller's telegram_id.
    No user can access another user's progress data.
    """
    return await ProgressService().get_progress(conn, telegram_id)
