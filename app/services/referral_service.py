from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncConnection
from uuid import UUID

from sqlalchemy import select, update, func
from app.models.user import User

class ReferralService:
    async def process_referral_on_user_upsert(
        self, conn: AsyncConnection, user_id: UUID, ref_code: UUID | None
    ) -> None:
        if not ref_code:
            return
        # Find the inviter who owns the ref_code
        inviter_id = await conn.scalar(select(User.id).where(User.invite_code == ref_code))
        if inviter_id and inviter_id != user_id:
            await conn.execute(
                update(User)
                .where(User.id == user_id)
                .values(invited_by_user_id=inviter_id)
            )

    async def credit_inviter_on_first_quiz_completion(
        self, conn: AsyncConnection, user_id: UUID
    ) -> None:
        # Get the user's inviter and current reward state
        result = await conn.execute(select(User.invited_by_user_id, User.referral_reward_state).where(User.id == user_id))
        row = result.fetchone()
        if not row or not row.invited_by_user_id:
            return
        
        # Check if already rewarded
        state = dict(row.referral_reward_state) if row.referral_reward_state else {}
        if state.get("first_quiz_credited"):
            return
            
        # Credit the inviter
        await conn.execute(
            update(User)
            .where(User.id == row.invited_by_user_id)
            .values(invite_count=User.invite_count + 1)
        )
        
        # Mark as credited for the invitee
        state["first_quiz_credited"] = True
        await conn.execute(
            update(User)
            .where(User.id == user_id)
            .values(referral_reward_state=state)
        )

    async def get_user_referral_stats(
        self, conn: AsyncConnection, user_id: UUID
    ) -> dict:
        result = await conn.execute(select(User.invite_count, User.invite_code).where(User.id == user_id))
        row = result.fetchone()
        if not row:
            return {"invite_count": 0, "invite_code": None}
        return {"invite_count": row.invite_count, "invite_code": row.invite_code}
