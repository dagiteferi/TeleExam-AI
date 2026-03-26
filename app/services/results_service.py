from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class ResultsService:
    async def get_summary(self, conn: AsyncConnection, *, telegram_id: int) -> dict[str, Any]:
        result = await conn.execute(
            text(
                """
                select
                    count(*) as total_exams_taken,
                    coalesce(avg(score::float), 0) as average_score
                from results r
                join users u on u.id = r.user_id
                where u.telegram_id = :telegram_id
                """
            ),
            {"telegram_id": telegram_id},
        )
        row = result.mappings().first() or {}

        sessions = await conn.execute(
            text(
                """
                select session_id, mode, expires_at
                from user_sessions us
                join users u on u.id = us.user_id
                where u.telegram_id = :telegram_id
                order by expires_at desc
                limit 10
                """
            ),
            {"telegram_id": telegram_id},
        )
        recent_sessions = [
            {"session_id": r["session_id"], "mode": r["mode"], "date": r["expires_at"].isoformat()}
            for r in sessions.mappings().all()
        ]

        return {
            "success": True,
            "total_exams_taken": int(row.get("total_exams_taken", 0) or 0),
            "average_score": float(row.get("average_score", 0) or 0),
            "weak_topics": [],
            "recent_sessions": recent_sessions,
        }

    async def get_session_details(self, conn: AsyncConnection, *, session_id: str) -> dict[str, Any]:
        sess = await conn.execute(
            text(
                """
                select us.session_id, us.mode, us.answers
                from user_sessions us
                where us.session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        row = sess.mappings().first()
        if not row:
            raise LookupError("Session not found")

        answers: list[dict[str, Any]] = row["answers"]
        total = len(answers)
        correct = sum(1 for a in answers if a.get("is_correct") is True)
        incorrect = sum(1 for a in answers if a.get("is_correct") is False)

        details = []
        for a in answers:
            qid = a.get("question_id")
            if not qid:
                continue
            q = await conn.execute(
                text(
                    """
                    select q.id, q.correct_answer, t.topic_name
                    from questions q
                    left join topics t on t.id = q.topic_id
                    where q.id = :qid
                    """
                ),
                {"qid": int(qid)},
            )
            qr = q.mappings().first() or {}
            details.append(
                {
                    "question_id": int(qid),
                    "user_answer": a.get("answer"),
                    "correct_answer": qr.get("correct_answer"),
                    "is_correct": a.get("is_correct"),
                    "topic": qr.get("topic_name"),
                }
            )

        return {
            "success": True,
            "session_id": row["session_id"],
            "mode": row["mode"],
            "score": correct,
            "total_questions": total,
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "questions_details": details,
        }

