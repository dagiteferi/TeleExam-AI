from __future__ import annotations
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.exam import StartExamResponse, NextQuestionResponse, AnswerResponse, StartExamResponseQuestion

class ExamService:
    async def start_session(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        mode: str,
        course_id: int | None = None,
        topic_id: int | None = None,
    ) -> StartExamResponse:
        # Pseudo-logic or minimal implementation logic
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        
        # Insert session logic here (using dummy data for now)
        question_id = 1
        text_content = "Dummy first question?"
        options = ["Option A", "Option B", "Option C"]
        total_questions = 10
        
        return StartExamResponse(
            session_id=session_id,
            total_questions=total_questions,
            next_question=StartExamResponseQuestion(
                question_id=question_id,
                text=text_content,
                options=options,
            )
        )

    async def get_next_question(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        session_id: str,
    ) -> NextQuestionResponse:
        # Dummy data
        return NextQuestionResponse(
            question_id=2,
            text="Dummy next question?",
            options=["A", "B", "C", "D"],
            image_url=None
        )

    async def submit_answer(
        self,
        conn: AsyncConnection,
        telegram_id: int,
        session_id: str,
        question_id: int,
        answer: str,
    ) -> AnswerResponse:
        is_correct = False
        correct_answer = "C"
        if answer == correct_answer:
            is_correct = True
            
        return AnswerResponse(
            success=True,
            is_correct=is_correct,
            correct_answer=correct_answer,
            feedback="Great job!" if is_correct else "Incorrect, try again."
        )
