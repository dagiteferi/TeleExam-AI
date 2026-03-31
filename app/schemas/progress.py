from __future__ import annotations
from pydantic import BaseModel


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


class ProgressResponse(BaseModel):
    """Full progress dashboard data — private to the authenticated user."""
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
