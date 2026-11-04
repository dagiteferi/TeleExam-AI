from __future__ import annotations
from pydantic import BaseModel
from datetime import date, datetime


class CourseProgress(BaseModel):
    """Per-course accuracy breakdown."""
    course_name: str
    total_answered: int
    correct: int
    wrong: int
    accuracy_percent: float


class WeakTopic(BaseModel):
    topic_name: str
    error_count: int  # wrong answers among the topic's recent answers
    attempted: int = 0  # recent answers the rate is based on
    error_rate_percent: float = 0.0


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


class HistoryItem(BaseModel):
    """One finished session in the results history."""
    session_id: str
    mode: str
    title: str
    score_percent: float
    correct_count: int
    wrong_count: int
    question_count: int
    duration_seconds: int
    submitted_at: datetime


class HistoryResponse(BaseModel):
    """A page of the user's results history, newest first."""
    department_name: str | None = None
    mode: str  # "all", "exam" or "practice"
    date_from: date | None = None  # day filter actually applied (inclusive)
    date_to: date | None = None
    page: int
    page_size: int
    total: int
    has_next: bool
    items: list[HistoryItem]


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
    # PRO features on the dashboard: full history, day filter, Review My Mistakes
    has_pro: bool = False
    mistakes_to_review: int = 0


class MistakesSummary(BaseModel):
    """What the Review My Mistakes button needs to know."""
    has_pro: bool
    count: int  # questions whose latest answer was wrong


class MistakeItem(BaseModel):
    """One question the student got wrong: question text only (no choices, no correct answer)."""
    question_id: str
    prompt: str  # shortened if very long
    your_answer: str  # the student's last (wrong) choice, used for the AI explanation
    course_name: str | None = None
    answered_at: datetime


class MistakeCourseCount(BaseModel):
    course_name: str
    count: int


class MistakeListResponse(BaseModel):
    """A page of the student's wrong questions plus a per-course summary."""
    total: int
    page: int
    page_size: int
    has_next: bool
    by_course: list[MistakeCourseCount] = []
    items: list[MistakeItem] = []

