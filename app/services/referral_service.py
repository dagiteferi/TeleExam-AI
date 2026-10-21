from __future__ import annotations
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.user import User

# Set on the invitee once their inviter has been credited.
# "first_quiz_credited" is the older key and is still honoured so nobody is credited twice.
CREDITED_KEY = "first_session_credited"
LEGACY_CREDITED_KEY = "first_quiz_credited"


class ReferralService:
    async def process_referral_on_user_upsert(
        self, conn: AsyncConnection, user_id: UUID, ref_code: UUID | None
    ) -> None:
        if not ref_code:
            return
        # Find the inviter who owns the ref_code
        result = await conn.execute(
            select(User.id, User.telegram_id)
            .where(User.invite_code == ref_code)
        )
        inviter = result.fetchone()

        if inviter and inviter.id != user_id:
            # Only link the invitee here; the inviter is credited once the invitee
            # starts their first session (see credit_inviter_on_first_session).
            await conn.execute(
                update(User)
                .where(User.id == user_id)
                .values(invited_by_user_id=inviter.id)
            )

    async def credit_inviter_on_first_session(
        self, conn: AsyncConnection, user_id: UUID
    ) -> None:
        """Credits the inviter with one invite the first time the invitee starts a quiz, exam or practice."""
        state = func.coalesce(User.referral_reward_state, func.jsonb_build_object(), type_=JSONB)
        # Mark the invitee as credited and get their inviter in one statement,
        # so two sessions started at the same time can't credit twice.
        result = await conn.execute(
            update(User)
            .where(
                User.id == user_id,
                User.invited_by_user_id.is_not(None),
                ~state.has_key(CREDITED_KEY),
                ~state.has_key(LEGACY_CREDITED_KEY),
            )
            .values(
                referral_reward_state=state.op("||")(func.jsonb_build_object(CREDITED_KEY, True))
            )
            .returning(User.invited_by_user_id)
        )
        row = result.fetchone()
        if not row:
            return

        await conn.execute(
            update(User)
            .where(User.id == row.invited_by_user_id)
            .values(invite_count=User.invite_count + 1)
        )

    async def get_user_referral_stats(
        self, conn: AsyncConnection, user_id: UUID
    ) -> dict:
        result = await conn.execute(select(User.invite_count, User.invite_code).where(User.id == user_id))
        row = result.fetchone()
        if not row:
            return {"invite_count": 0, "invite_code": None}
        return {"invite_count": row.invite_count, "invite_code": row.invite_code}
