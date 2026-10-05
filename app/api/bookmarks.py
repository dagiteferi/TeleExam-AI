from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

from app.api.deps import get_db_conn, get_current_telegram_id
from app.db.postgres import db_conn
from app.schemas.bookmark import BookmarkCreateResponse, BookmarkListResponse, BookmarkResponse
from app.models.bookmark import Bookmark
from sqlalchemy import select, delete, insert
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
                delete(Bookmark).where(Bookmark.id == existing)
            )
            await conn.commit()
            return BookmarkCreateResponse(success=True, message="Bookmark removed")
        else:
            # Create bookmark
            res = await conn.execute(
                insert(Bookmark)
                .values(user_id=user_id, question_id=question_id)
                .returning(Bookmark.id)
            )
            new_bookmark_id = res.scalar_one()
            await conn.commit()
            return BookmarkCreateResponse(success=True, message="Question safely bookmarked!", bookmark_id=new_bookmark_id)
            
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
    # Get bookmarks with question data using explicit columns for AsyncConnection
    stmt = (
        select(
            Bookmark.id,
            Bookmark.question_id,
            Bookmark.user_id,
            Bookmark.created_at,
            Question.prompt,
            Question.choice_a,
            Question.choice_b,
            Question.choice_c,
            Question.choice_d,
            Question.correct_choice,
        )
        .join(Question, Bookmark.question_id == Question.id)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
    )
    result = await conn.execute(stmt)
    
    items = []
    for row in result.mappings().all():
        items.append(BookmarkResponse.model_validate(dict(row)))
    
    return BookmarkListResponse(items=items)
