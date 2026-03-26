from __future__ import annotations
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    telegram_id: int
    question_id: UUID # Changed to UUID
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


class StudyPlanTopic(BaseModel):
    name: str
    resources: list[str] = Field(default_factory=list)


class StudyPlanDetails(BaseModel):
    title: str
    duration_days: int
    topics: list[StudyPlanTopic] = Field(default_factory=list)


class StudyPlanRequest(BaseModel):
    telegram_id: int


class StudyPlanResponse(BaseModel):
    success: bool = True
    study_plan: StudyPlanDetails
