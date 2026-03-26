from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


Mode = Literal["exam", "practice", "quiz"]


class StartExamResponseQuestion(BaseModel):
    question_id: int
    text: str
    options: list[str] = Field(default_factory=list)
    image_url: str | None = None


class StartExamResponse(BaseModel):
    session_id: str
    total_questions: int
    next_question: StartExamResponseQuestion


class NextQuestionResponse(BaseModel):
    question_id: int
    text: str
    options: list[str] = Field(default_factory=list)
    image_url: str | None = None


class AnswerRequest(BaseModel):
    session_id: str
    question_id: int
    answer: str


class AnswerResponse(BaseModel):
    success: bool = True
    is_correct: bool
    correct_answer: str
    feedback: str

