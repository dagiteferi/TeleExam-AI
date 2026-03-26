from __future__ import annotations
from fastapi import APIRouter, Depends
from app.api.deps import get_current_telegram_id
from app.models.response import SuccessResponse

router = APIRouter(prefix="/users")


@router.post("/upsert", response_model=SuccessResponse)
async def upsert_user(telegram_id: int = Depends(get_current_telegram_id)) -> SuccessResponse:
    # Placeholder until DB/services are wired in next step.
    return SuccessResponse(success=True, data={"telegram_id": telegram_id})

