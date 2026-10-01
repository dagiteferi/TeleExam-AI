"""
app/admin/exams.py

Full CRUD admin endpoints for:
  - Past Exams    → /admin/exams/past-exams
  - Questions     → /admin/exams/questions
  - Exam Templates→ /admin/exams/templates

Support (dropdown data):
  - Departments   → /admin/exams/departments
  - Courses       → /admin/exams/courses
  - Topics        → /admin/exams/topics

All routes require the `manage_content` permission (or superadmin).
"""
from __future__ import annotations

import hashlib
import uuid
import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import select, update, delete, func, insert, text

from app.admin.deps import require_permission, get_admin_db
from app.models.department import Department
from app.models.course import Course
from app.models.topic import Topic
from app.models.past_exam import PastExam, PastExamQuestion
from app.models.question import Question
from app.models.exam_template import ExamTemplate, ExamTemplateTopic
from app.schemas.admin import (
    DepartmentListItem,
    CourseListItem,
    TopicListItem,
    PastExamCreate,
    PastExamUpdate,
    PastExamResponse,
    QuestionCreate,
    QuestionUpdate,
    QuestionAdminResponse,
    ExamTemplateCreate,
    ExamTemplateUpdate,
    ExamTemplateResponse,
    ExamTemplateTopicResponse,
)

router = APIRouter(
    prefix="/exams",
    dependencies=[Depends(require_permission("manage_content"))],
)

_NOT_FOUND = lambda entity: HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"error": {"code": "not_found", "message": f"{entity} not found"}},
)


# ─────────────────────────────────────────────────────────────
#  Support — Departments / Courses / Topics (dropdown data)
# ─────────────────────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentListItem])
async def list_departments(
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[DepartmentListItem]:
    result = await conn.execute(select(Department).order_by(Department.name))
    return [DepartmentListItem(**row) for row in result.mappings()]


@router.get("/courses", response_model=list[CourseListItem])
async def list_courses(
    department_id: UUID | None = None,
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[CourseListItem]:
    q = select(Course).order_by(Course.name)
    if department_id:
        q = q.where(Course.department_id == department_id)
    result = await conn.execute(q)
    return [CourseListItem(**row) for row in result.mappings()]


@router.get("/topics", response_model=list[TopicListItem])
async def list_topics(
    course_id: UUID | None = None,
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[TopicListItem]:
    q = select(Topic).order_by(Topic.name)
    if course_id:
        q = q.where(Topic.course_id == course_id)
    result = await conn.execute(q)
    return [TopicListItem(**row) for row in result.mappings()]


# ─────────────────────────────────────────────────────────────
#  Past Exams
# ─────────────────────────────────────────────────────────────

async def _build_past_exam_response(row: dict, conn: AsyncConnection) -> PastExamResponse:
    """Enriches a raw past_exam row with department_name, course_name, question_count."""
    dept_result = await conn.execute(select(Department.name).where(Department.id == row["department_id"]))
    dept_name = dept_result.scalar_one_or_none()

    course_name = None
    if row["course_id"]:
        course_result = await conn.execute(select(Course.name).where(Course.id == row["course_id"]))
        course_name = course_result.scalar_one_or_none()

    count_result = await conn.execute(
        select(func.count()).where(PastExamQuestion.past_exam_id == row["id"])
    )
    question_count = count_result.scalar() or 0

    return PastExamResponse(
        **row,
        department_name=dept_name,
        course_name=course_name,
        question_count=question_count,
    )


@router.get("/past-exams", response_model=list[PastExamResponse])
async def list_past_exams(
    department_id: UUID | None = None,
    course_id: UUID | None = None,
    year: int | None = None,
    limit: int = 50,
    offset: int = 0,
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[PastExamResponse]:
    q = select(PastExam).order_by(PastExam.year.desc()).limit(limit).offset(offset)
    if department_id:
        q = q.where(PastExam.department_id == department_id)
    if course_id:
        q = q.where(PastExam.course_id == course_id)
    if year:
        q = q.where(PastExam.year == year)

    result = await conn.execute(q)
    rows = result.mappings().all()
    return [await _build_past_exam_response(dict(r), conn) for r in rows]


@router.get("/past-exams/{exam_id}", response_model=PastExamResponse)
async def get_past_exam(
    exam_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PastExamResponse:
    result = await conn.execute(select(PastExam).where(PastExam.id == exam_id))
    row = result.mappings().one_or_none()
    if not row:
        raise _NOT_FOUND("Past exam")
    return await _build_past_exam_response(dict(row), conn)


@router.post("/past-exams", response_model=PastExamResponse, status_code=status.HTTP_201_CREATED)
async def create_past_exam(
    body: PastExamCreate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PastExamResponse:
    new_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    await conn.execute(
        insert(PastExam).values(
            id=new_id,
            department_id=body.department_id,
            course_id=body.course_id,
            year=body.year,
            semester=body.semester,
            created_at=now,
        )
    )
    await conn.commit()
    result = await conn.execute(select(PastExam).where(PastExam.id == new_id))
    row = result.mappings().one()
    return await _build_past_exam_response(dict(row), conn)


@router.patch("/past-exams/{exam_id}", response_model=PastExamResponse)
async def update_past_exam(
    exam_id: UUID,
    body: PastExamUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> PastExamResponse:
    values = body.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="No fields to update")
    await conn.execute(update(PastExam).where(PastExam.id == exam_id).values(**values))
    await conn.commit()
    result = await conn.execute(select(PastExam).where(PastExam.id == exam_id))
    row = result.mappings().one_or_none()
    if not row:
        raise _NOT_FOUND("Past exam")
    return await _build_past_exam_response(dict(row), conn)


@router.delete("/past-exams/{exam_id}")
async def delete_past_exam(
    exam_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
):
    # Remove junction rows first, then the exam itself
    await conn.execute(delete(PastExamQuestion).where(PastExamQuestion.past_exam_id == exam_id))
    result = await conn.execute(delete(PastExam).where(PastExam.id == exam_id))
    await conn.commit()
    if result.rowcount == 0:
        raise _NOT_FOUND("Past exam")
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────
#  Questions
# ─────────────────────────────────────────────────────────────

async def _enrich_question(row: dict, conn: AsyncConnection) -> QuestionAdminResponse:
    course_result = await conn.execute(select(Course.name).where(Course.id == row["course_id"]))
    course_name = course_result.scalar_one_or_none()
    topic_result = await conn.execute(select(Topic.name).where(Topic.id == row["topic_id"]))
    topic_name = topic_result.scalar_one_or_none()
    return QuestionAdminResponse(**row, course_name=course_name, topic_name=topic_name)


@router.get("/questions", response_model=list[QuestionAdminResponse])
async def list_questions(
    course_id: UUID | None = None,
    topic_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[QuestionAdminResponse]:
    q = select(Question).order_by(Question.created_at.desc()).limit(limit).offset(offset)
    if course_id:
        q = q.where(Question.course_id == course_id)
    if topic_id:
        q = q.where(Question.topic_id == topic_id)
    if is_active is not None:
        q = q.where(Question.is_active == is_active)
    if search:
        q = q.where(Question.prompt.ilike(f"%{search}%"))

    result = await conn.execute(q)
    rows = result.mappings().all()
    return [await _enrich_question(dict(r), conn) for r in rows]


@router.get("/questions/{question_id}", response_model=QuestionAdminResponse)
async def get_question(
    question_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> QuestionAdminResponse:
    result = await conn.execute(select(Question).where(Question.id == question_id))
    row = result.mappings().one_or_none()
    if not row:
        raise _NOT_FOUND("Question")
    return await _enrich_question(dict(row), conn)


@router.post("/questions", response_model=QuestionAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> QuestionAdminResponse:
    # Compute content_hash (idempotent guard) from prompt + choices
    raw = f"{body.prompt}{body.choice_a}{body.choice_b}{body.choice_c}{body.choice_d}".encode()
    content_hash = hashlib.sha256(raw).digest()

    new_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        await conn.execute(
            insert(Question).values(
                id=new_id,
                course_id=body.course_id,
                topic_id=body.topic_id,
                format="mcq",
                prompt=body.prompt,
                choice_a=body.choice_a,
                choice_b=body.choice_b,
                choice_c=body.choice_c,
                choice_d=body.choice_d,
                correct_choice=body.correct_choice,
                difficulty=body.difficulty,
                source=body.source,
                explanation_static=body.explanation_static,
                is_active=body.is_active,
                content_hash=content_hash,
                created_at=now,
                updated_at=now,
            )
        )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        if "uq_question_content_hash" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "duplicate_question", "message": "A question with identical content already exists"}},
            )
        raise

    result = await conn.execute(select(Question).where(Question.id == new_id))
    row = result.mappings().one()
    return await _enrich_question(dict(row), conn)


@router.patch("/questions/{question_id}", response_model=QuestionAdminResponse)
async def update_question(
    question_id: UUID,
    body: QuestionUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> QuestionAdminResponse:
    values = body.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="No fields to update")
    values["updated_at"] = datetime.datetime.now(datetime.timezone.utc)

    # Recompute content_hash if any content field changed
    content_fields = {"prompt", "choice_a", "choice_b", "choice_c", "choice_d"}
    if content_fields & set(values.keys()):
        # Fetch current row to fill in unchanged fields
        current_result = await conn.execute(select(Question).where(Question.id == question_id))
        current = current_result.mappings().one_or_none()
        if not current:
            raise _NOT_FOUND("Question")
        merged = {k: values.get(k, current[k]) for k in ["prompt", "choice_a", "choice_b", "choice_c", "choice_d"]}
        raw = "".join(merged.values()).encode()
        values["content_hash"] = hashlib.sha256(raw).digest()

    await conn.execute(update(Question).where(Question.id == question_id).values(**values))
    await conn.commit()
    result = await conn.execute(select(Question).where(Question.id == question_id))
    row = result.mappings().one_or_none()
    if not row:
        raise _NOT_FOUND("Question")
    return await _enrich_question(dict(row), conn)


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: UUID,
    hard: bool = False,   # ?hard=true does a real DELETE, default is soft-delete
    conn: AsyncConnection = Depends(get_admin_db),
):
    if hard:
        result = await conn.execute(delete(Question).where(Question.id == question_id))
        await conn.commit()
        if result.rowcount == 0:
            raise _NOT_FOUND("Question")
    else:
        # Soft-delete: set is_active = False
        result = await conn.execute(
            update(Question).where(Question.id == question_id).values(is_active=False)
        )
        await conn.commit()
        if result.rowcount == 0:
            raise _NOT_FOUND("Question")
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────
#  Exam Templates
# ─────────────────────────────────────────────────────────────

async def _enrich_template(row: dict, conn: AsyncConnection) -> ExamTemplateResponse:
    course_result = await conn.execute(select(Course.name).where(Course.id == row["course_id"]))
    course_name = course_result.scalar_one_or_none()

    topics_result = await conn.execute(
        select(ExamTemplateTopic.topic_id, ExamTemplateTopic.weight, Topic.name.label("topic_name"))
        .join(Topic, ExamTemplateTopic.topic_id == Topic.id)
        .where(ExamTemplateTopic.exam_template_id == row["id"])
    )
    topics = [
        ExamTemplateTopicResponse(topic_id=t.topic_id, topic_name=t.topic_name, weight=float(t.weight))
        for t in topics_result
    ]
    return ExamTemplateResponse(**row, course_name=course_name, topics=topics)


@router.get("/templates", response_model=list[ExamTemplateResponse])
async def list_exam_templates(
    course_id: UUID | None = None,
    mode: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    conn: AsyncConnection = Depends(get_admin_db),
) -> list[ExamTemplateResponse]:
    q = select(ExamTemplate).order_by(ExamTemplate.created_at.desc()).limit(limit).offset(offset)
    if course_id:
        q = q.where(ExamTemplate.course_id == course_id)
    if mode:
        q = q.where(ExamTemplate.mode == mode)
    if is_active is not None:
        q = q.where(ExamTemplate.is_active == is_active)

    result = await conn.execute(q)
    rows = result.mappings().all()
    return [await _enrich_template(dict(r), conn) for r in rows]


@router.get("/templates/{template_id}", response_model=ExamTemplateResponse)
async def get_exam_template(
    template_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
) -> ExamTemplateResponse:
    result = await conn.execute(select(ExamTemplate).where(ExamTemplate.id == template_id))
    row = result.mappings().one_or_none()
    if not row:
        raise _NOT_FOUND("Exam template")
    return await _enrich_template(dict(row), conn)


@router.post("/templates", response_model=ExamTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_exam_template(
    body: ExamTemplateCreate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> ExamTemplateResponse:
    new_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    await conn.execute(
        insert(ExamTemplate).values(
            id=new_id,
            course_id=body.course_id,
            code=body.code,
            name=body.name,
            mode=body.mode,
            question_count=body.question_count,
            duration_seconds=body.duration_seconds,
            is_active=body.is_active,
            created_at=now,
        )
    )
    # Insert topic associations
    for t in body.topics:
        await conn.execute(
            insert(ExamTemplateTopic).values(
                exam_template_id=new_id,
                topic_id=t.topic_id,
                weight=t.weight,
            )
        )
    await conn.commit()

    result = await conn.execute(select(ExamTemplate).where(ExamTemplate.id == new_id))
    row = result.mappings().one()
    return await _enrich_template(dict(row), conn)


@router.patch("/templates/{template_id}", response_model=ExamTemplateResponse)
async def update_exam_template(
    template_id: UUID,
    body: ExamTemplateUpdate,
    conn: AsyncConnection = Depends(get_admin_db),
) -> ExamTemplateResponse:
    values = body.model_dump(exclude_unset=True, exclude={"topics"})
    if values:
        await conn.execute(update(ExamTemplate).where(ExamTemplate.id == template_id).values(**values))

    # Replace topics if provided
    if body.topics is not None:
        await conn.execute(delete(ExamTemplateTopic).where(ExamTemplateTopic.exam_template_id == template_id))
        for t in body.topics:
            await conn.execute(
                insert(ExamTemplateTopic).values(
                    exam_template_id=template_id,
                    topic_id=t.topic_id,
                    weight=t.weight,
                )
            )

    await conn.commit()
    result = await conn.execute(select(ExamTemplate).where(ExamTemplate.id == template_id))
    row = result.mappings().one_or_none()
    if not row:
        raise _NOT_FOUND("Exam template")
    return await _enrich_template(dict(row), conn)


@router.delete("/templates/{template_id}")
async def delete_exam_template(
    template_id: UUID,
    conn: AsyncConnection = Depends(get_admin_db),
):
    await conn.execute(delete(ExamTemplateTopic).where(ExamTemplateTopic.exam_template_id == template_id))
    result = await conn.execute(delete(ExamTemplate).where(ExamTemplate.id == template_id))
    await conn.commit()
    if result.rowcount == 0:
        raise _NOT_FOUND("Exam template")
    return {"status": "ok"}
