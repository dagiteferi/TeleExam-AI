import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select

from app.api.deps import get_public_db_conn
from app.models.department import Department
from app.models.past_exam import PastExam
from app.models.course import Course
from app.models.app_setting import AppSetting

router = APIRouter(prefix="/public")

@router.get("/discovery-metadata")
async def get_discovery_metadata(
    conn: Annotated[AsyncConnection, Depends(get_public_db_conn)],
    department_id: uuid.UUID | None = None,
) -> dict:
    """Publicly accessible metadata for the frontend selection menus."""
    
 
    dept_stmt = select(Department.id, Department.name).where(Department.is_active == True)
    depts_res = await conn.execute(dept_stmt)
    departments = [{"id": row.id, "name": row.name} for row in depts_res]
 
    exam_stmt = (
        select(PastExam.department_id, PastExam.year, PastExam.semester)
        .distinct()
        .order_by(PastExam.year.desc())
    )
    exams_res = await conn.execute(exam_stmt)
    exams_metadata = [
        {"department_id": row.department_id, "year": row.year, "semester": row.semester}
        for row in exams_res
    ]

    course_stmt = select(Course.name).distinct().where(Course.is_active == True)
    if department_id:
        course_stmt = course_stmt.where(Course.department_id == department_id)
        
    courses_res = await conn.execute(course_stmt)
    available_courses = [row.name for row in courses_res]

    return {
        "departments": departments,
        "exams": exams_metadata,
        "courses": available_courses,
        "info": "Selection metadata for TeleExam AI discovery"
    }


@router.get("/settings")
async def get_public_settings(
    conn: Annotated[AsyncConnection, Depends(get_public_db_conn)],
) -> dict:
    """
    Returns all public app settings as a flat key-value dictionary.
    Only settings marked is_public=True are returned.
    """
    stmt = select(AppSetting.key, AppSetting.value).where(AppSetting.is_public == True)
    result = await conn.execute(stmt)
    settings_map = {}
    for row in result:
        val = row.value
        if row.key == "support_contact_url" and val:
            v_strip = val.strip()
            if not (v_strip.startswith("http://") or v_strip.startswith("https://") or v_strip.startswith("tg://")):
                val = f"https://t.me/{v_strip[1:]}" if v_strip.startswith("@") else f"https://t.me/{v_strip}"
        settings_map[row.key] = val
    return settings_map

