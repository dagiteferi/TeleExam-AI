from __future__ import annotations
from fastapi import APIRouter
from app.api.user import router as user_router
from app.api.session import router as session_router

api_router = APIRouter(prefix="/api")
api_router.include_router(user_router, tags=["users"])
api_router.include_router(session_router, tags=["session"])

