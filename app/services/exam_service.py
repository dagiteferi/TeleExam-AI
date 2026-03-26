from __future__ import annotations
import uuid
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


Mode = Literal["exam", "practice", "quiz"]


class ExamService:
    async def start_session(
        self,
        conn: AsyncConnection,
        *,
        telegram_id: int,
        mode: Mode,
        course_id: int | None,
        topic_id: int | None,
    ) -> dict[str, Any]:
        user_id = await self._ensure_user(conn, telegram_id=telegram_id)

        if mode == "exam":
            if course_id is None:
                raise ValueError("course_id is required for exam mode")
            exam = await self._select_exam(conn, course_id=course_id)
            exam_id = exam["exam_id"]
            question_ids = await self._list_exam_question_ids(conn, exam_id=exam_id)
        else:
            if topic_id is None:
                raise ValueError("topic_id is required for practice/quiz mode")
            exam_id = None
            question_ids = await self._list_topic_question_ids(conn, topic_id=topic_id, limit=25)

        if not question_ids:
            raise LookupError("No questions found")

        session_id = f"sess_{uuid.uuid4().hex}"
        answers = [{"question_id": qid, "answer": None, "is_correct": None} for qid in question_ids]

        await conn.execute(
            text(
                """
                insert into user_sessions (session_id, user_id, exam_id, current_index, answers, mode)
                values (:session_id, :user_id, :exam_id, 0, cast(:answers as jsonb), :mode)
                """
            ),
            {
                "session_id": session_id,
                "user_id": user_id,
                "exam_id": exam_id,
                "answers": __import__("json").dumps(answers),
                "mode": mode,
            },
        )
        await conn.commit()

        first_question = await self._get_question(conn, question_id=question_ids[0])
        return {
            "session_id": session_id,
            "total_questions": len(question_ids),
            "next_question": first_question,
        }

    async def next_question(self, conn: AsyncConnection, *, session_id: str) -> dict[str, Any]:
        session = await self._get_session(conn, session_id=session_id)
        answers: list[dict[str, Any]] = session["answers"]
        idx = int(session["current_index"])
        if idx >= len(answers):
            raise LookupError("Session completed")
        question_id = int(answers[idx]["question_id"])
        return await self._get_question(conn, question_id=question_id)

    async def submit_answer(
        self,
        conn: AsyncConnection,
        *,
        session_id: str,
        question_id: int,
        answer: str,
    ) -> dict[str, Any]:
        session = await self._get_session(conn, session_id=session_id)
        answers: list[dict[str, Any]] = session["answers"]
        idx = int(session["current_index"])
        if idx >= len(answers):
            raise LookupError("Session completed")

        expected_qid = int(answers[idx]["question_id"])
        if expected_qid != question_id:
            raise ValueError("question_id does not match the current question")

        question = await self._get_question_row(conn, question_id=question_id)
        correct_answer = str(question["correct_answer"])
        is_correct = answer.strip().upper() == correct_answer.strip().upper()

        answers[idx] = {"question_id": question_id, "answer": answer, "is_correct": is_correct}
        new_idx = idx + 1

        await conn.execute(
            text(
                """
                update user_sessions
                set answers = cast(:answers as jsonb),
                    current_index = :new_idx
                where session_id = :session_id
                """
            ),
            {
                "answers": __import__("json").dumps(answers),
                "new_idx": new_idx,
                "session_id": session_id,
            },
        )
        await conn.commit()

        feedback = "Correct!" if is_correct else "Incorrect."
        if not is_correct and question.get("explanation"):
            feedback = f"{feedback} {question['explanation']}"

        return {
            "success": True,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "feedback": feedback,
        }

    async def _ensure_user(self, conn: AsyncConnection, *, telegram_id: int) -> int:
        result = await conn.execute(
            text(
                """
                insert into users (telegram_id)
                values (:telegram_id)
                on conflict (telegram_id) do update set telegram_id = excluded.telegram_id
                returning id
                """
            ),
            {"telegram_id": telegram_id},
        )
        row = result.mappings().first()
        if not row:
            raise RuntimeError("Failed to create user")
        return int(row["id"])

    async def _select_exam(self, conn: AsyncConnection, *, course_id: int) -> dict[str, Any]:
        result = await conn.execute(
            text(
                """
                select id as exam_id, year, semester
                from exams
                where course_id = :course_id
                order by year desc, semester desc
                limit 1
                """
            ),
            {"course_id": course_id},
        )
        row = result.mappings().first()
        if not row:
            raise LookupError("Exam not found for course")
        return dict(row)

    async def _list_exam_question_ids(self, conn: AsyncConnection, *, exam_id: int) -> list[int]:
        result = await conn.execute(
            text(
                """
                select eq.question_id
                from exam_questions eq
                where eq.exam_id = :exam_id
                order by eq.question_id asc
                """
            ),
            {"exam_id": exam_id},
        )
        return [int(r[0]) for r in result.fetchall()]

    async def _list_topic_question_ids(
        self, conn: AsyncConnection, *, topic_id: int, limit: int
    ) -> list[int]:
        result = await conn.execute(
            text(
                """
                select q.id
                from questions q
                where q.topic_id = :topic_id
                order by q.id asc
                limit :limit
                """
            ),
            {"topic_id": topic_id, "limit": limit},
        )
        return [int(r[0]) for r in result.fetchall()]

    async def _get_session(self, conn: AsyncConnection, *, session_id: str) -> dict[str, Any]:
        result = await conn.execute(
            text(
                """
                select session_id, current_index, answers, mode, exam_id
                from user_sessions
                where session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        row = result.mappings().first()
        if not row:
            raise LookupError("Session not found")
        return dict(row)

    async def _get_question(self, conn: AsyncConnection, *, question_id: int) -> dict[str, Any]:
        row = await self._get_question_row(conn, question_id=question_id)
        options = row["options"]
        if isinstance(options, str):
            options = __import__("json").loads(options)
        return {
            "question_id": int(row["id"]),
            "text": str(row["question_text"]),
            "options": options,
            "image_url": None,
        }

    async def _get_question_row(self, conn: AsyncConnection, *, question_id: int) -> dict[str, Any]:
        result = await conn.execute(
            text(
                """
                select id, question_text, options, correct_answer, explanation, topic_id
                from questions
                where id = :question_id
                """
            ),
            {"question_id": question_id},
        )
        row = result.mappings().first()
        if not row:
            raise LookupError("Question not found")
        return dict(row)

