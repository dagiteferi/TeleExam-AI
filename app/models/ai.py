from __future__ import annotations
from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    telegram_id: int
    question_id: int
    user_answer: str | None = None


class ExplainResponse(BaseModel):
    success: bool = True
    explanation: str
    key_points: list[str] = Field(default_factory=list)
    weak_topic_suggestion: str | None = None


class ChatRequest(BaseModel):
    telegram_id: int
    message: str


class ChatResponse(BaseModel):
    success: bool = True
    ai_response: str

