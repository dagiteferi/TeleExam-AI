from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

from app.api.deps import get_db_conn, get_current_telegram_id
from app.db.postgres import db_conn
from app.schemas.bookmark import BookmarkCreateResponse, BookmarkListResponse, BookmarkResponse
from app.models.bookmark import Bookmark
from sqlalchemy import select, delete
from app.models.user import User

router = APIRouter(
    prefix="/bookmarks",
    tags=["Bookmarks"],
)

# Endpoint will be mounted at /api/bookmarks

@router.post("/{question_id}", response_model=BookmarkCreateResponse)
async def toggle_bookmark_question(
    question_id: UUID,
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn)
):
    """
    Toggles a bookmark for a specific question (creates if it doesn't exist, deletes if it does).
    """
    
    
    user_result = await conn.execute(select(User.id).where(User.telegram_id == telegram_id))
    user_id = user_result.scalar_one_or_none()
    
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    try:
        # Check if already bookmarked
        existing_result = await conn.execute(
            select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.question_id == question_id)
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Delete bookmark
            await conn.execute(
                delete(Bookmark).where(Bookmark.id == existing.id)
            )
            await conn.commit()
            return BookmarkCreateResponse(success=True, message="Bookmark removed")
        else:
            # Create bookmark
            new_bookmark = Bookmark(user_id=user_id, question_id=question_id)
            conn.add(new_bookmark)
            await conn.commit()
            return BookmarkCreateResponse(success=True, message="Question safely bookmarked!", bookmark_id=new_bookmark.id)
            
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=BookmarkListResponse)
async def get_my_bookmarks(
    telegram_id: int = Depends(get_current_telegram_id),
    conn: AsyncConnection = Depends(get_db_conn)
):
    """
    Gets all bookmarks for the user.
    """
    from app.models.user import User
    user_result = await conn.execute(select(User.id).where(User.telegram_id == telegram_id))
    user_id = user_result.scalar_one_or_none()
    
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    from app.models.question import Question
    # Get bookmarks with question data
    stmt = (
        select(Bookmark, Question)
        .join(Question, Bookmark.question_id == Question.id)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
    )
    result = await conn.execute(stmt)
    
    items = []
    for bookmark, question in result.all():
        b_dict = {
            "id": bookmark.id,
            "question_id": bookmark.question_id,
            "user_id": bookmark.user_id,
            "created_at": bookmark.created_at,
            "prompt": question.prompt,
            "choice_a": question.choice_a,
            "choice_b": question.choice_b,
            "choice_c": question.choice_c,
            "choice_d": question.choice_d,
            "correct_choice": question.correct_choice,
        }
        items.append(BookmarkResponse.model_validate(b_dict))
    
    return BookmarkListResponse(items=items)
