from __future__ import annotations

import uuid
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import UUID

from app.models.user import User
from app.schemas.users import UserUpsertRequest


class UserService:
    async def upsert_user(self, conn: AsyncConnection, *, telegram_id: int, user_data: UserUpsertRequest) -> User:
        # Check if user exists
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await conn.execute(stmt)
        existing_user = result.scalar_one_or_none()

        from app.services.referral_service import ReferralService
        referral_service = ReferralService()
        
        if existing_user:
            # Update existing user
            update_data = user_data.model_dump(exclude_unset=True, exclude={'ref_code'})
            if update_data:
                user = await conn.scalar(
                    update(User).where(User.telegram_id == telegram_id).values(**update_data).returning(User)
                )
            else:
                user = existing_user
        else:
            # Create new user
            insert_data = user_data.model_dump(exclude={'ref_code'})
            user = await conn.scalar(insert(User).values(**insert_data).returning(User))
            
            # Process referral ONLY for NEW users
            if user_data.ref_code:
                await referral_service.process_referral_on_user_upsert(conn, user.id, user_data.ref_code)

        await conn.commit()
        return user