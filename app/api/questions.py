from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_telegram_id, get_db_conn
from app.services.question_service import QuestionService
from pydantic import BaseModel, UUID4

router = APIRouter(prefix="/questions")

class QuestionItem(BaseModel):
    id: UUID4
    prompt: str
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    correct_choice: str | None = None
    explanation: str | None = None
    year: int
    course_id: UUID4
    course_name: str
    topic_name: str

class DiscoveryResponse(BaseModel):
    questions: list[QuestionItem]
    total_count: int

@router.get("/by-exam", response_model=DiscoveryResponse)
async def get_questions_by_exam(
    department_id: UUID4,
    year: int | None = None,
    semester: str | None = None,
    mode: Literal["exam", "practice"] = "practice",
    telegram_id: Annotated[int, Depends(get_current_telegram_id)] = None,
    conn: Annotated[AsyncConnection, Depends(get_db_conn)] = None,
) -> DiscoveryResponse:
    """Get questions filtered by department, year, and semester."""
    return await QuestionService().get_questions(
        conn, department_id=department_id, year=year, semester=semester, mode=mode
    )

@router.get("/by-course", response_model=DiscoveryResponse)
async def get_questions_by_course(
    course_name: str,
    mode: Literal["exam", "practice"] = "practice",
    telegram_id: Annotated[int, Depends(get_current_telegram_id)] = None,
    conn: Annotated[AsyncConnection, Depends(get_db_conn)] = None,
) -> DiscoveryResponse:
    """Get questions for a specific course across all available years."""
    return await QuestionService().get_questions(
        conn, course_name_search=course_name, mode=mode
    )

@router.get("/discovery/courses")
async def get_available_courses(
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> list[dict]:
    """Get unique course names available across all exams."""
    return await QuestionService().get_available_courses(conn)

@router.get("/discovery/departments")
async def get_available_departments(
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> list[dict]:
    """Get all departments."""
    return await QuestionService().get_available_departments(conn)

@router.get("/discovery/department/{department_id}/exams")
async def get_exams_by_department(
    department_id: UUID4,
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
) -> list[dict]:
    """Get all available years and semesters for a specific department."""
    return await QuestionService().get_exams_by_department(conn, department_id)
