from __future__ import annotations

import uuid
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import UUID

from app.models.user import User
from app.schemas.users import UserUpsertRequest


class UserService:
    async def upsert_user(self, conn: AsyncConnection, *, telegram_id: int, user_data: UserUpsertRequest) -> User:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        
        # Check existence to know if referral processing is needed (to avoid re-applying rewards)
        stmt = select(User.id).where(User.telegram_id == telegram_id)
        result = await conn.execute(stmt)
        existing_user_id = result.scalar_one_or_none()
        is_new = existing_user_id is None

        # Build upsert logic with PostgreSQL's ON CONFLICT
        insert_data = user_data.model_dump(exclude={'ref_code'})
        # Ensure we use the authorized telegram_id from the dependency
        insert_data["telegram_id"] = telegram_id
        
        # Fields to update if conflict occurs (exclude ID and telegram_id)
        update_data = {k: v for k, v in insert_data.items() if k not in ["id", "telegram_id"] and v is not None}

        async with conn.begin():
            stmt = (
                pg_insert(User)
                .values(**insert_data)
                .on_conflict_do_update(
                    index_elements=[User.telegram_id],
                    set_=update_data
                )
                .returning(User)
            )
            
            result = await conn.execute(stmt)
            user = result.one() # Get the full row

            # Handle referral only for NEW users
            if is_new and user_data.ref_code:
                from app.services.referral_service import ReferralService
                await ReferralService().process_referral_on_user_upsert(conn, user.id, user_data.ref_code)
        
        return user