from __future__ import annotations
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, bool]:
    return {"ok": True}

