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
from app.models.department import Department
from app.models.course import Course
from app.models.topic import Topic
from app.models.question import Question
from app.models.past_exam import PastExam, PastExamQuestion
from app.models.exam_template import ExamTemplate, ExamTemplateTopic
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

    def _armor_text(self, text: str) -> str:
        """Injects zero-width space between every character to hinder scraping."""
        if not text:
            return ""
        return "\u200b".join(list(text))

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

            if request.past_exam_id:
                # NEW: Start session based on a specific Past Exam
                questions = await conn.scalars(
                    select(Question.id)
                    .join(PastExamQuestion, Question.id == PastExamQuestion.question_id)
                    .where(PastExamQuestion.past_exam_id == request.past_exam_id, Question.is_active == True)
                )
                question_ids = questions.all()
                total_questions = len(question_ids)
                if total_questions == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={"error": {"code": "no_questions_found", "message": "No questions found for the selected past exam."}},
                    )
                session_ttl_seconds = settings.DEFAULT_EXAM_TTL_SECONDS
                deadline_ts = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=session_ttl_seconds)).timestamp()
            else:
                # DEFAULT: Start session based on an Exam Template
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
                
                # For now, fetch course questions
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
                
                # Shuffle and slice
                rng = random.Random(seed)
                rng.shuffle(question_ids)
                question_ids = question_ids[:exam_template.question_count]
                total_questions = len(question_ids)

                session_ttl_seconds = exam_template.duration_seconds + settings.EXAM_GRACE_PERIOD_SECONDS if exam_template.duration_seconds else settings.DEFAULT_EXAM_TTL_SECONDS
                deadline_ts = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=exam_template.duration_seconds)).timestamp() if exam_template.duration_seconds else None
            
            # Common Shuffle for Past Exam if desired
            if request.past_exam_id:
                rng = random.Random(seed)
                rng.shuffle(question_ids)

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
            
            rng = random.Random(seed)
            rng.shuffle(question_ids)
            session_ttl_seconds = settings.DEFAULT_PRACTICE_TTL_SECONDS

            session_ttl_seconds = settings.DEFAULT_EXAM_TTL_SECONDS
            # Optionally add a deadline based on question count if template is missing
            deadline_ts = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=total_questions * 90)).timestamp() 

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
        # Filter out None values for Redis hset mapping
        filtered_session_data = {k: v for k, v in session_data.items() if v is not None}
        await self.redis.hset(session_key, mapping=filtered_session_data)
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
            deadline_ts=int(deadline_ts) if deadline_ts else None,
        )

    async def get_session_metadata(self, session_id: uuid.UUID, telegram_id: int) -> dict:
        session_key = get_session_key(str(session_id))
        session_data = await self.redis.hgetall(session_key)
        
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "session_not_found", "message": "Session not found."}}
            )
        
        if int(session_data["telegram_id"]) != telegram_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "access_denied", "message": "Access denied."}}
            )

        # Convert simple types for return
        return {
            "session_id": str(session_id),
            "status": session_data.get("status"),
            "mode": session_data.get("mode"),
            "current_index": int(session_data.get("current_index", 0)),
            "total_questions": int(session_data.get("total_questions", 0)),
            "deadline_ts": int(float(session_data.get("deadline_ts"))) if session_data.get("deadline_ts") else None,
            "start_time": session_data.get("start_time"),
        }

    async def get_question(self, conn: AsyncConnection, telegram_id: int, session_id: uuid.UUID) -> GetQuestionResponse:
        session_key = get_session_key(str(session_id))
        session_data = await self.redis.hgetall(session_key)
        
        if not session_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "session_not_found", "message": "Session not found."}})
        
        if int(session_data["telegram_id"]) != telegram_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "access_denied", "message": "Access denied."}})

        if session_data["status"] != "in_progress":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "invalid_status", "message": f"Session status is {session_data['status']}"}})

        # Deadline check
        if session_data.get("deadline_ts"):
            import time
            if time.time() > float(session_data["deadline_ts"]):
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "session_expired", "message": "The exam deadline has passed."}})

        current_index = int(session_data["current_index"])
        question_ids = json.loads(session_data["question_ids"])
        
        if current_index >= len(question_ids):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "end_of_session", "message": "No more questions."}})
            
        question_uuid = question_ids[current_index]
        result = await conn.execute(select(Question).where(Question.id == question_uuid))
        question = result.one_or_none()
        
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "question_not_found", "message": "Question data unavailable."}})

        # Issue qtoken
        import secrets
        qtoken = secrets.token_urlsafe(16)
        qtoken_key = get_qtoken_key(session_data["user_id"], str(session_id), question_uuid)
        await self.redis.set(qtoken_key, qtoken, ex=settings.QTOKEN_TTL_SECONDS)
        
        # Track served time
        served_time_key = get_question_served_time_key(str(session_id), current_index)
        await self.redis.set(served_time_key, datetime.datetime.now(datetime.timezone.utc).timestamp(), ex=3600)

        # Build payload
        payload = QuestionPayload(
            question_id=uuid.UUID(question_uuid),
            index=current_index,
            total=int(session_data["total_questions"]),
            prompt=self._armor_text(question.prompt),
            image_url=None, # Removed as per request
            choice_a=question.choice_a,
            choice_b=question.choice_b,
            choice_c=question.choice_c,
            choice_d=question.choice_d,
            qtoken=qtoken
        )
        
        return GetQuestionResponse(session_id=session_id, question=payload)

    async def submit_answer(self, conn: AsyncConnection, telegram_id: int, session_id: uuid.UUID, request: SubmitAnswerRequest) -> SubmitAnswerResponse:
        session_key = get_session_key(str(session_id))
        session_data = await self.redis.hgetall(session_key)
        
        if not session_data or session_data["status"] != "in_progress":
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "session_inactive", "message": "Session is inactive."}})

        # Deadline check
        if session_data.get("deadline_ts"):
            import time
            if time.time() > float(session_data["deadline_ts"]):
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "session_expired", "message": "The exam deadline has passed."}})

        current_index = int(session_data["current_index"])
        question_ids = json.loads(session_data["question_ids"])
        current_question_id = question_ids[current_index]
        
        if str(request.question_id) != current_question_id:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "question_mismatch", "message": "Out of sync."}})

        # Validate qtoken
        qtoken_key = get_qtoken_key(session_data["user_id"], str(session_id), current_question_id)
        stored_token = await self.redis.get(qtoken_key)
        if not stored_token or stored_token != request.qtoken:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "invalid_qtoken", "message": "Token expired or invalid."}})
        
        await self.redis.delete(qtoken_key) # single-use

        # Save answer
        answers = json.loads(session_data["answers"])
        answers[str(request.question_id)] = {
            "selected_choice": request.answer,
            "answered_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        await self.redis.hset(session_key, "answers", json.dumps(answers))
        
        # Immediate feedback for practice/quiz
        is_correct = None
        explanation = None
        if session_data["mode"] != "exam":
            result = await conn.execute(select(Question).where(Question.id == request.question_id))
            question = result.one_or_none()
            if question:
                is_correct = (request.answer == question.correct_choice)
                explanation = question.explanation_static
                answers[str(request.question_id)]["is_correct"] = is_correct
            # Update Redis with correctness for summary later
            await self.redis.hset(session_key, "answers", json.dumps(answers))

        return SubmitAnswerResponse(accepted=True, is_correct=is_correct, explanation=explanation)

    async def next_question(self, conn: AsyncConnection, telegram_id: int, session_id: uuid.UUID) -> NextResponse:
        session_key = get_session_key(str(session_id))
        session_data = await self.redis.hgetall(session_key)
        
        if not session_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        current_index = int(session_data["current_index"])
        total = int(session_data["total_questions"])
        
        if current_index + 1 >= total:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "limit_reached", "message": "No more questions."}})

        # Increment index
        new_index = current_index + 1
        await self.redis.hset(session_key, "current_index", new_index)
        
        return NextResponse(session_id=session_id, index=new_index)

    async def submit_session(self, conn: AsyncConnection, telegram_id: int, session_id: uuid.UUID) -> SubmitSessionResponse:
        from app.models.exam_result import ExamResult
        from app.models.user_answer import UserAnswer
        
        session_key = get_session_key(str(session_id))
        session_data = await self.redis.hgetall(session_key)
        
        if not session_data or session_data["status"] == "completed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": {"code": "already_submitted"}})

        answers_dict = json.loads(session_data["answers"])
        question_ids = json.loads(session_data["question_ids"])
        
        # Map correct answers from DB
        questions_db = await conn.execute(select(Question.id, Question.correct_choice, Question.topic_id).where(Question.id.in_(question_ids)))
        q_map = {str(r.id): {"correct": r.correct_choice, "topic": r.topic_id} for r in questions_db}
        
        from app.services.analytics_service import AnalyticsService
        from app.services.referral_service import ReferralService
        analytics = AnalyticsService()
        
        correct_count = 0
        wrong_count = 0
        for q_id, ans in answers_dict.items():
            if q_id in q_map:
                is_correct = (ans["selected_choice"] == q_map[q_id]["correct"])
                ans["is_correct"] = is_correct
                if is_correct:
                    correct_count += 1
                else:
                    wrong_count += 1
                    # Record topic error for analytics
                    await analytics.record_user_topic_error(conn, uuid.UUID(session_data["user_id"]), q_map[q_id]["topic"])
        
        score_percent = (correct_count / len(question_ids)) * 100 if question_ids else 0
        
        # Referral logic: credit inviter if first quiz completion
        if session_data["mode"] == "quiz":
            await ReferralService().credit_inviter_on_first_quiz_completion(conn, uuid.UUID(session_data["user_id"]))
        
        # Persist Result to Postgres
        from sqlalchemy import insert
        res_stmt = insert(ExamResult).values(
            id=session_id,
            user_id=uuid.UUID(session_data["user_id"]),
            course_id=uuid.UUID(session_data["course_id"]) if session_data.get("course_id") else None,
            mode=session_data["mode"],
            question_count=len(question_ids),
            correct_count=correct_count,
            wrong_count=wrong_count,
            score_percent=score_percent,
            started_at=datetime.datetime.fromisoformat(session_data["start_time"]),
            submitted_at=datetime.datetime.now(datetime.timezone.utc),
            duration_seconds=int((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(session_data["start_time"])).total_seconds()),
            metadata_={"seed": session_data["seed"]}
        )
        
        await conn.execute(res_stmt)

        # Bulk insert answers
        if answers_dict:
            answers_stmt = insert(UserAnswer).values([
                {
                    "id": uuid.uuid4(),
                    "exam_result_id": session_id,
                    "user_id": uuid.UUID(session_data["user_id"]),
                    "question_id": uuid.UUID(q_id),
                    "topic_id": q_map[q_id]["topic"],
                    "selected_choice": ans["selected_choice"],
                    "is_correct": ans["is_correct"],
                    "answered_at": datetime.datetime.fromisoformat(ans["answered_at"])
                }
                for q_id, ans in answers_dict.items() if q_id in q_map
            ])
            await conn.execute(answers_stmt)
        
        # Mark as completed in Redis
        await self.redis.hset(session_key, "status", "completed")
        # Pointer cleanup
        active_key = get_active_session_key(uuid.UUID(session_data["user_id"]), session_data["mode"])
        await self.redis.delete(active_key)

        return SubmitSessionResponse(
            session_id=session_id,
            mode=session_data["mode"],
            question_count=len(question_ids),
            correct_count=correct_count,
            wrong_count=wrong_count,
            score_percent=score_percent,
            submitted_at=datetime.datetime.now(datetime.timezone.utc)
        )

