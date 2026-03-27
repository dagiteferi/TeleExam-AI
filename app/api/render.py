from __future__ import annotations

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select

from app.db.postgres import db_conn
from app.api.deps import get_public_db_conn
from app.models.question import Question
from app.services.render_service import RenderService

router = APIRouter(prefix="/v1/render", tags=["Render"])

@router.get("/{question_id}.png")
async def render_question_image(
    question_id: uuid.UUID,
    conn: Annotated[AsyncConnection, Depends(get_public_db_conn)],
):
    """
    Returns the question prompt content as a PNG image to prevent text copying.
    """
    # 1. Fetch Question content
    result = await conn.execute(select(Question.prompt).where(Question.id == question_id))
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    # 2. Render image from prompt
    img_data = RenderService.render_question_text(prompt)
    
    return Response(content=img_data, media_type="image/png")
