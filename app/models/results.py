from __future__ import annotations
from pydantic import BaseModel, Field

from uuid import UUID

class SessionResultDetail(BaseModel):
    question_id: UUID
    user_answer: str
    correct_answer: str
    is_correct: bool
    topic: str

class SessionResultResponse(BaseModel):
    success: bool = True
    session_id: str
    mode: str
    score: int
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    questions_details: list[SessionResultDetail] = Field(default_factory=list)

class RecentSessionSummary(BaseModel):
    session_id: str
    score: int
    date: str

class OverallResultsResponse(BaseModel):
    success: bool = True
    total_exams_taken: int
    average_score: float
    weak_topics: list[str] = Field(default_factory=list)
    recent_sessions: list[RecentSessionSummary] = Field(default_factory=list)
