from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class ResultsSummaryResponse(BaseModel):
    success: bool = True
    total_exams_taken: int
    average_score: float
    weak_topics: list[str] = Field(default_factory=list)
    recent_sessions: list[dict[str, Any]] = Field(default_factory=list)


class SessionDetailsResponse(BaseModel):
    success: bool = True
    session_id: str
    mode: str
    score: int
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    questions_details: list[dict[str, Any]] = Field(default_factory=list)

