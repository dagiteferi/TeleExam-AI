from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

class ReferralService:
    async def process_referral_on_user_upsert(
        self, conn: AsyncConnection, user_id: UUID, ref_code: UUID | None
    ) -> None:
        pass

    async def credit_inviter_on_first_quiz_completion(
        self, conn: AsyncConnection, user_id: UUID
    ) -> None:
        pass

    async def get_user_referral_stats(
        self, conn: AsyncConnection, user_id: UUID
    ) -> dict:
        return {"invite_count": 0, "rewards_unlocked": []}
