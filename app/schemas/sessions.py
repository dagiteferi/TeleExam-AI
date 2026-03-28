from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


SessionMode = Literal["exam", "practice", "quiz"]


class StartSessionRequest(BaseModel):
    mode: SessionMode
    department_id: UUID | None = None
    course_id: UUID | None = None
    topic_id: UUID | None = None
    past_exam_id: UUID | None = None
    exam_template_id: UUID | None = None
    question_count: int | None = Field(default=None, ge=5, le=10)  # quiz only


class StartSessionResponse(BaseModel):
    session_id: UUID
    mode: SessionMode
    status: Literal["in_progress"]
    question_count: int
    ttl_seconds: int
    deadline_ts: int | None = None


class QuestionPayload(BaseModel):
    question_id: UUID
    index: int
    total: int
    prompt: str | None = None
    image_url: str | None = None  # exam mode: required; practice/quiz: usually null
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    qtoken: str  # mandatory; short-lived; single-use


class GetQuestionResponse(BaseModel):
    session_id: UUID
    question: QuestionPayload


class SubmitAnswerRequest(BaseModel):
    question_id: UUID
    answer: Literal["A", "B", "C", "D"]
    qtoken: str


class SubmitAnswerResponse(BaseModel):
    accepted: bool = True
    is_correct: bool | None = None  # practice/quiz only
    explanation: str | None = None  # practice/quiz only


class NextResponse(BaseModel):
    session_id: UUID
    index: int


class SubmitSessionResponse(BaseModel):
    session_id: UUID
    mode: SessionMode
    question_count: int
    correct_count: int
    wrong_count: int
    score_percent: float
    submitted_at: datetime
    per_topic_breakdown: list[dict] | None = None
