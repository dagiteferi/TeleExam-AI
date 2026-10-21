from __future__ import annotations
import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.user import User
from app.services.invitation_service import InvitationService
from app.core.notify import send_telegram_message


class ReferralService:
    async def _check_and_grant_pro_reward(
        self, conn: AsyncConnection, inviter_id: UUID
    ) -> None:
        """Checks if the inviter reached the threshold to earn PRO access as a reward."""
        config = await InvitationService.get_config(conn)
        if config.pro_reward_invite_threshold <= 0:
            return

        res = await conn.execute(
            select(User.invite_count, User.is_pro, User.telegram_id, User.first_name)
            .where(User.id == inviter_id)
        )
        row = res.fetchone()
        if not row or row.is_pro or row.invite_count < config.pro_reward_invite_threshold:
            return

        plan_expiry = None
        if config.pro_reward_days > 0:
            plan_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=config.pro_reward_days)

        await conn.execute(
            update(User)
            .where(User.id == inviter_id)
            .values(is_pro=True, plan_expiry=plan_expiry)
        )

        if row.telegram_id:
            duration_text = f"for {config.pro_reward_days} days" if config.pro_reward_days > 0 else "permanently"
            await send_telegram_message(
                row.telegram_id,
                f"🎁 <b>Congratulations, {row.first_name or 'there'}! You unlocked PRO access {duration_text}!</b>\n\n"
                f"You have invited {row.invite_count} friends to TeleExam AI.\n"
                "As an invitation reward, your account has been upgraded to <b>PRO</b>!\n\n"
                "• Unlimited AI explanations\n"
                "• All course exams unlocked\n"
                "• Full access across the platform! 🎉",
                refresh_menu=True,
            )

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
            # 1. Update the invitee's record
            await conn.execute(
                update(User)
                .where(User.id == user_id)
                .values(invited_by_user_id=inviter.id)
            )
            
            # 2. Check if admin configured signup credit
            config = await InvitationService.get_config(conn)
            if config.credit_on_signup:
                await conn.execute(
                    update(User)
                    .where(User.id == inviter.id)
                    .values(invite_count=User.invite_count + 1)
                )
                await self._check_and_grant_pro_reward(conn, inviter.id)

    async def credit_inviter_on_first_quiz_completion(
        self, conn: AsyncConnection, user_id: UUID
    ) -> None:
        config = await InvitationService.get_config(conn)
        if not config.credit_on_first_quiz:
            return

        # Get the user's inviter and current reward state
        result = await conn.execute(
            select(User.invited_by_user_id, User.referral_reward_state).where(User.id == user_id)
        )
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

        await self._check_and_grant_pro_reward(conn, row.invited_by_user_id)

    async def get_user_referral_stats(
        self, conn: AsyncConnection, user_id: UUID
    ) -> dict:
        result = await conn.execute(select(User.invite_count, User.invite_code).where(User.id == user_id))
        row = result.fetchone()
        if not row:
            return {"invite_count": 0, "invite_code": None}
        return {"invite_count": row.invite_count, "invite_code": row.invite_code}
