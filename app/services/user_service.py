from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class UserService:
    async def upsert_user(self, conn: AsyncConnection, *, telegram_id: int) -> dict:
        result = await conn.execute(
            text(
                """
                insert into users (telegram_id)
                values (:telegram_id)
                on conflict (telegram_id)
                do update set telegram_id = excluded.telegram_id
                returning id, pro_status
                """
            ),
            {"telegram_id": telegram_id},
        )
        row = result.mappings().first()
        if not row:
            raise RuntimeError("Failed to upsert user")
        return {"user_id": int(row["id"]), "pro_status": bool(row["pro_status"])}

