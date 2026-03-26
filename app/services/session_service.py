from __future__ import annotations

import datetime
import json
import random
import uuid
from typing import Literal

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from fastapi import HTTPException, status

from app.db.redis import (
    get_session_key,
    get_active_session_key,
    get_qtoken_key,
    get_question_served_time_key,
)
from app.models.course import Course
from app.models.exam_template import ExamTemplate, ExamTemplateTopic
from app.models.question import Question
from app.models.user import User
from app.schemas.sessions import (
    SessionMode,
    StartSessionRequest,
    StartSessionResponse,
    QuestionPayload,
    GetQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    NextResponse,
    SubmitSessionResponse,
)
from app.core.config import settings

logger = structlog.get_logger(__name__)


class SessionService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def start_session(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        user_id: uuid.UUID,
        request: StartSessionRequest,
    ) -> StartSessionResponse:
        # 1. Enforce single active session per user per mode
        active_session_key = get_active_session_key(user_id, request.mode)
        existing_session_id = await self.redis.get(active_session_key)

        if existing_session_id:
            # Check if the existing session is still valid
            session_data = await self.redis.hgetall(get_session_key(existing_session_id))
            if session_data and session_data.get("status") == "in_progress":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "active_session_exists",
                            "message": f"An active {request.mode} session already exists.",
                            "session_id": existing_session_id,
                        }
                    },
                )
            else:
                # Clean up stale active session pointer
                await self.redis.delete(active_session_key)

        # 2. Validate user eligibility and retrieve questions
        question_ids: list[uuid.UUID] = []
        total_questions: int = 0
        session_ttl_seconds: int = 0
        deadline_ts: float | None = None # Changed to float for timestamp
        seed = random.randint(0, 2**32 - 1) # For deterministic randomization

        if request.mode == "exam":
            if not request.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "missing_course_id", "message": "course_id is required for exam mode"}},
                )
            exam_template = await conn.scalar(
                select(ExamTemplate).where(
                    ExamTemplate.course_id == request.course_id, ExamTemplate.mode == "exam", ExamTemplate.is_active == True
                )
            )
            if not exam_template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "exam_template_not_found", "message": "No active exam template found for the given course."}},
                )
            
            # Fetch questions based on exam template topics and weights
            # For simplicity, let's fetch all questions for the course for now
            # TODO: Implement weighted question selection based on ExamTemplateTopic
            questions = await conn.scalars(
                select(Question.id).where(Question.course_id == request.course_id, Question.is_active == True)
            )
            question_ids = questions.all()
            total_questions = len(question_ids)
            if total_questions < exam_template.question_count:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "not_enough_questions", "message": "Not enough active questions available for this exam."}},
                )
            
            # Shuffle questions deterministically
            rng = random.Random(seed)
            rng.shuffle(question_ids)
            question_ids = question_ids[:exam_template.question_count]
            total_questions = len(question_ids)

            session_ttl_seconds = exam_template.duration_seconds + settings.EXAM_GRACE_PERIOD_SECONDS if exam_template.duration_seconds else settings.DEFAULT_EXAM_TTL_SECONDS
            deadline_ts = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=exam_template.duration_seconds)).timestamp() if exam_template.duration_seconds else None

        elif request.mode == "practice":
            if not request.topic_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "missing_topic_id", "message": "topic_id is required for practice mode"}},
                )
            questions = await conn.scalars(
                select(Question.id).where(Question.topic_id == request.topic_id, Question.is_active == True)
            )
            question_ids = questions.all()
            total_questions = len(question_ids)
            if total_questions == 0:
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "no_questions_found", "message": "No active questions found for this topic."}},
                )
            
            # Shuffle questions deterministically
            rng = random.Random(seed)
            rng.shuffle(question_ids)

            session_ttl_seconds = settings.DEFAULT_PRACTICE_TTL_SECONDS

        elif request.mode == "quiz":
            if not request.topic_id and not request.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "missing_topic_or_course_id", "message": "topic_id or course_id is required for quiz mode"}},
                )
            
            # For quiz, either topic_id or course_id can be used
            if request.topic_id:
                questions = await conn.scalars(
                    select(Question.id).where(Question.topic_id == request.topic_id, Question.is_active == True)
                )
            elif request.course_id:
                questions = await conn.scalars(
                    select(Question.id).where(Question.course_id == request.course_id, Question.is_active == True)
                )
            else:
                # Should not happen due to previous check
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "invalid_quiz_params", "message": "Invalid parameters for quiz mode."}},
                )
            
            question_ids = questions.all()
            total_questions = len(question_ids)
            if total_questions == 0:
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "no_questions_found", "message": "No active questions found for this quiz."}},
                )
            
            # Shuffle questions deterministically
            rng = random.Random(seed)
            rng.shuffle(question_ids)

            if request.question_count:
                question_ids = question_ids[:request.question_count]
                total_questions = len(question_ids)
            else:
                # Default quiz question count
                question_ids = question_ids[:settings.DEFAULT_QUIZ_QUESTION_COUNT]
                total_questions = len(question_ids)

            session_ttl_seconds = settings.DEFAULT_QUIZ_TTL_SECONDS
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "invalid_mode", "message": "Invalid session mode specified."}},
            )

        if not question_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "no_questions_found", "message": "No questions found for the selected criteria."}},
            )

        # 3. Create session in Redis
        session_id = str(uuid.uuid4())
        session_key = get_session_key(session_id)
        start_time = datetime.datetime.now(datetime.timezone.utc)

        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "telegram_id": telegram_id,
            "mode": request.mode,
            "status": "in_progress",
            "question_ids": json.dumps([str(q_id) for q_id in question_ids]),
            "current_index": 0,
            "answers": json.dumps({}),
            "start_time": start_time.isoformat(),
            "deadline_ts": deadline_ts,
            "topic_id": str(request.topic_id) if request.topic_id else None,
            "course_id": str(request.course_id) if request.course_id else None,
            "exam_template_id": str(request.exam_template_id) if request.exam_template_id else None,
            "seed": seed,
            "total_questions": total_questions,
        }

        # Store session data in Redis Hash
        await self.redis.hset(session_key, mapping=session_data)
        await self.redis.expire(session_key, session_ttl_seconds)

        # Set active session pointer with SETNX
        setnx_result = await self.redis.setnx(active_session_key, session_id)
        if not setnx_result:
            # This case should ideally be caught earlier, but as a fallback
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "active_session_exists",
                        "message": f"An active {request.mode} session already exists (SETNX failed).",
                        "session_id": existing_session_id,
                    }
                },
            )
        await self.redis.expire(active_session_key, session_ttl_seconds) # Align TTL

        logger.info("Session started", session_id=session_id, user_id=str(user_id), mode=request.mode, total_questions=total_questions)

        return StartSessionResponse(
            session_id=uuid.UUID(session_id),
            mode=request.mode,
            status="in_progress",
            question_count=total_questions,
            ttl_seconds=session_ttl_seconds,
            deadline_ts=int(deadline_ts) if deadline_ts else None,
        )
