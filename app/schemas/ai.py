from __future__ import annotations
from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    question_id: str
    user_answer: str | None = None


class ExplainResponse(BaseModel):
    success: bool = True
    explanation: str
    key_points: list[str] = Field(default_factory=list)
    weak_topic_suggestion: str | None = None


class ChatRequest(BaseModel):
    message: str
    question_id: str


class ChatResponse(BaseModel):
    success: bool = True
    ai_response: str


# --- Study Plan ---

class StudyTopic(BaseModel):
    topic: str
    errors: int
    focus: str  # e.g. "High Priority", "Medium", "Review"


class StudyDay(BaseModel):
    day: int
    topic: str
    action: str  # e.g. "Read + Practice", "Solve past questions"


class StudyPlanDetails(BaseModel):
    summary: str  # e.g. "You scored 62% overall. Weak in Databases, OS."
    total_exams_done: int
    overall_score_percent: float
    weak_topics: list[StudyTopic] = Field(default_factory=list)
    daily_plan: list[StudyDay] = Field(default_factory=list)


class StudyPlanRequest(BaseModel):
    pass


class StudyPlanResponse(BaseModel):
    success: bool = True
    study_plan: StudyPlanDetails | None = None
    message: str | None = None  # For prereq failures or user-facing notes
