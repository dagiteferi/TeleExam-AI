from __future__ import annotations
from fastapi import APIRouter
from app.api.user import router as user_router
from app.api.session import router as session_router
from app.api.exam import router as exam_router
from app.api.results import router as results_router
from app.api.ai import router as ai_router

api_router = APIRouter(prefix="/api")
api_router.include_router(user_router, tags=["users"])
api_router.include_router(session_router, tags=["session"])
api_router.include_router(exam_router, tags=["exam"])
api_router.include_router(results_router, tags=["results"])
api_router.include_router(ai_router, tags=["ai"])

