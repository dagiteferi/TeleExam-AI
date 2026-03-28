from __future__ import annotations
from fastapi import APIRouter, Depends
from app.api.deps import telegram_secret_header, telegram_id_header
from app.api.user import router as user_router
# from app.api.session import router as session_router # Removed
# from app.api.exam import router as exam_router # Removed
from app.api.sessions import router as sessions_router # Added
from app.api.results import router as results_router
from app.api.ai import router as ai_router
from app.api.questions import router as questions_router

api_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(telegram_secret_header), Depends(telegram_id_header)]
)
api_router.include_router(user_router, tags=["users"])
# api_router.include_router(session_router, tags=["session"]) # Removed
# api_router.include_router(exam_router, tags=["exam"]) # Removed
api_router.include_router(sessions_router, tags=["sessions"]) # Added
api_router.include_router(results_router, tags=["results"])
api_router.include_router(ai_router, tags=["ai"])
api_router.include_router(questions_router, tags=["discovery"])