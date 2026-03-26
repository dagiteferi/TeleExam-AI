from __future__ import annotations
from pydantic import BaseModel, Field


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
