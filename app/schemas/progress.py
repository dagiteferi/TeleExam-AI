from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime


class CourseProgress(BaseModel):
    """Per-course accuracy breakdown."""
    course_name: str
    total_answered: int
    correct: int
    wrong: int
    accuracy_percent: float


class WeakTopic(BaseModel):
    topic_name: str
    error_count: int


class TopExamScore(BaseModel):
    title: str
    top_score_percent: float
    total_questions: int


class ActiveSessionInfo(BaseModel):
    mode: str
    title: str
    current_question_index: int
    total_questions: int
    answered_count: int = 0


class RecentSession(BaseModel):
    mode: str
    title: str
    score_percent: float
    question_count: int
    answered_count: int = 0
    submitted_at: datetime


class ProgressResponse(BaseModel):
    """Full progress dashboard data — private to the authenticated user."""
    # Department the numbers belong to (dual-degree students switch between two)
    department_name: str | None = None
    total_exams_taken: int
    total_practice_sessions: int
    overall_accuracy_percent: float
    total_questions_answered: int
    total_correct: int
    total_wrong: int
    course_breakdown: list[CourseProgress]
    weak_topics: list[WeakTopic]
    # Trend: last 5 exam scores in chronological order
    recent_exam_scores: list[float]
    top_exam_scores: list[TopExamScore] = []
    active_session_info: ActiveSessionInfo | None = None
    recent_sessions: list[RecentSession] = []

