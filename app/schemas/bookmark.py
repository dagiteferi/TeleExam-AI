from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class BookmarkResponse(BaseModel):
    id: UUID
    question_id: UUID
    user_id: UUID
    created_at: datetime
    
    # Optional question details when joined
    prompt: Optional[str] = None
    choice_a: Optional[str] = None
    choice_b: Optional[str] = None
    choice_c: Optional[str] = None
    choice_d: Optional[str] = None
    correct_choice: Optional[str] = None
    
    class Config:
        from_attributes = True

class BookmarkCreateResponse(BaseModel):
    success: bool
    message: str
    bookmark_id: Optional[UUID] = None

class BookmarkListResponse(BaseModel):
    items: list[BookmarkResponse]
