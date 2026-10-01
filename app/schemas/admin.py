from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from enum import Enum

class AdminPermission(str, Enum):
    view_users = "view_users"
    ban_user = "ban_user"
    view_stats = "view_stats"
    manage_content = "manage_content"


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


class AdminUserResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    email: str
    role: str
    permissions: list[AdminPermission] = []
    invited_by_email: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class InviteAdminRequest(BaseModel):
    email: str
    permissions: list[AdminPermission] = []  # Converts to multiple-select dropdown in Swagger


class InviteAdminResponse(BaseModel):
    email: str
    password: str  
    permissions: list[AdminPermission]
    message: str


class UserAdminUpdate(BaseModel):
    is_pro: bool | None = None
    plan_expiry: datetime | None = None
    is_banned: bool | None = None
    ban_reason: str | None = None


class DailyActiveUser(BaseModel):
    day: datetime
    dau: int

class DAUResponse(BaseModel):
    data: list[DailyActiveUser]

class PlatformUserResponse(BaseModel):
    id: UUID
    telegram_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    invited_by_user_id: UUID | None = None
    invite_count: int = 0
    is_pro: bool
    is_full_access: bool
    plan_expiry: datetime | None = None
    is_banned: bool
    ban_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TopInviter(BaseModel):
    user_id: UUID
    telegram_id: int
    telegram_username: str | None = None
    invite_count: int

class ReferralStatsResponse(BaseModel):
    top_inviters: list[TopInviter]

class ExamStatsResponse(BaseModel):
    total_exams: int
    total_users: int
    average_score: float

class QuestionStatsResponse(BaseModel):
    question_id: UUID
    prompt: str
    correct_answer_count: int
    total_answer_count: int
    accuracy: float

class UserFlaggedResponse(BaseModel):
    user_id: UUID
    telegram_id: int
    is_banned_pg: bool
    ban_reason_pg: str | None = None
    flag_redis: str | None = None


class GrantFullAccessRequest(BaseModel):
    telegram_id: int


class GrantFullAccessResponse(BaseModel):
    telegram_id: int
    is_full_access: bool
    message: str

class DashboardSummaryResponse(BaseModel):
    total_users: int
    user_growth_percent: float
    total_exams: int
    today_dau: int
    banned_users: int
    chart_data: list[DailyActiveUser]


# ─── Exam Management Schemas ──────────────────────────────────────────────────

class DepartmentListItem(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool

class CourseListItem(BaseModel):
    id: UUID
    department_id: UUID
    code: str
    name: str
    is_active: bool

class TopicListItem(BaseModel):
    id: UUID
    course_id: UUID
    code: str
    name: str


# ── Past Exams ──

class PastExamCreate(BaseModel):
    department_id: UUID
    course_id: UUID | None = None
    year: int
    semester: str  # e.g. "1", "2", "annual"

class PastExamUpdate(BaseModel):
    department_id: UUID | None = None
    course_id: UUID | None = None
    year: int | None = None
    semester: str | None = None

class PastExamResponse(BaseModel):
    id: UUID
    department_id: UUID
    course_id: UUID | None = None
    year: int
    semester: str
    created_at: datetime
    question_count: int = 0          # populated in the query
    department_name: str | None = None
    course_name: str | None = None


# ── Questions ──

class QuestionCreate(BaseModel):
    course_id: UUID
    topic_id: UUID
    prompt: str
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    correct_choice: Literal["A", "B", "C", "D"]
    difficulty: int | None = None    # 1–5
    source: str | None = None
    explanation_static: str | None = None
    is_active: bool = True

class QuestionUpdate(BaseModel):
    course_id: UUID | None = None
    topic_id: UUID | None = None
    prompt: str | None = None
    choice_a: str | None = None
    choice_b: str | None = None
    choice_c: str | None = None
    choice_d: str | None = None
    correct_choice: Literal["A", "B", "C", "D"] | None = None
    difficulty: int | None = None
    source: str | None = None
    explanation_static: str | None = None
    is_active: bool | None = None

class QuestionAdminResponse(BaseModel):
    id: UUID
    course_id: UUID
    topic_id: UUID
    format: str
    prompt: str
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    correct_choice: str
    difficulty: int | None = None
    source: str | None = None
    explanation_static: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    course_name: str | None = None
    topic_name: str | None = None


# ── Exam Templates ──

class ExamTemplateTopicInput(BaseModel):
    topic_id: UUID
    weight: float = 1.0

class ExamTemplateCreate(BaseModel):
    course_id: UUID
    code: str
    name: str
    mode: Literal["exam", "quiz"]
    question_count: int
    duration_seconds: int | None = None
    is_active: bool = True
    topics: list[ExamTemplateTopicInput] = []

class ExamTemplateUpdate(BaseModel):
    course_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    mode: Literal["exam", "quiz"] | None = None
    question_count: int | None = None
    duration_seconds: int | None = None
    is_active: bool | None = None
    topics: list[ExamTemplateTopicInput] | None = None  # None = don't change

class ExamTemplateTopicResponse(BaseModel):
    topic_id: UUID
    topic_name: str | None = None
    weight: float

class ExamTemplateResponse(BaseModel):
    id: UUID
    course_id: UUID
    code: str
    name: str
    mode: str
    question_count: int
    duration_seconds: int | None = None
    is_active: bool
    created_at: datetime
    course_name: str | None = None
    topics: list[ExamTemplateTopicResponse] = []