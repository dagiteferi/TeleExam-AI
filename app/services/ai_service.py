from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class AiService:
    async def explain(
        self,
        conn: AsyncConnection,
        *,
        question_id: int,
        user_answer: str | None,
    ) -> dict[str, Any]:
        result = await conn.execute(
            text(
                """
                select question_text, correct_answer, explanation
                from questions
                where id = :qid
                """
            ),
            {"qid": question_id},
        )
        row = result.mappings().first()
        if not row:
            raise LookupError("Question not found")

        correct = str(row["correct_answer"])
        base = row.get("explanation") or "No stored explanation available yet."

        if user_answer:
            prefix = "Your answer is correct." if user_answer.strip().upper() == correct.strip().upper() else "Your answer is incorrect."
            explanation = f"{prefix} {base}"
        else:
            explanation = str(base)

        return {
            "success": True,
            "explanation": explanation,
            "key_points": [],
            "weak_topic_suggestion": None,
        }

    async def chat(self, *, message: str) -> dict[str, Any]:
        return {"success": True, "ai_response": message}

