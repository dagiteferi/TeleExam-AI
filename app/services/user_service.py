from __future__ import annotations

import uuid
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.dialects.postgresql import UUID

from app.models.user import User
from app.schemas.users import UserUpsertRequest


class UserService:
    async def get_user_by_telegram_id(self, conn: AsyncConnection, telegram_id: int):
        stmt = select(
            User.id,
            User.telegram_id,
            User.invite_code,
            User.invite_count,
            User.is_pro,
            User.plan_expiry,
            User.department_id,
        ).where(User.telegram_id == telegram_id)
        result = await conn.execute(stmt)
        return result.fetchone()

    async def upsert_user(self, conn: AsyncConnection, *, telegram_id: int, user_data: UserUpsertRequest):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        
        try:
            # Check existence inside the transaction to determine if referral is needed and if department is already locked
            stmt = select(User.id, User.department_id).where(User.telegram_id == telegram_id)
            result = await conn.execute(stmt)
            existing_user = result.fetchone()
            is_new = existing_user is None

            # Build upsert logic with PostgreSQL's ON CONFLICT
            insert_data = user_data.model_dump(exclude={'ref_code'})
            insert_data["telegram_id"] = telegram_id
            
            # ONE-TIME DEPARTMENT LOCK: If existing user already has a department set, do NOT allow changing it!
            if existing_user and existing_user.department_id is not None:
                insert_data.pop("department_id", None)

            # Fields to update if conflict occurs (exclude ID and telegram_id)
            update_data = {k: v for k, v in insert_data.items() if k not in ["id", "telegram_id"] and v is not None}

            insert_stmt = pg_insert(User).values(**insert_data)
            
            returning_cols = (
                User.id,
                User.telegram_id,
                User.invite_code,
                User.invite_count,
                User.is_pro,
                User.plan_expiry,
                User.department_id,
            )

            if not update_data:
                # If no data to update, just do nothing on conflict
                stmt = insert_stmt.on_conflict_do_nothing().returning(*returning_cols)
            else:
                # Standard upsert
                stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[User.telegram_id],
                    set_=update_data
                ).returning(*returning_cols)
            
            result = await conn.execute(stmt)
            user_row = result.fetchone()
            
            if user_row is None:
                # Fetch existing user explicitly
                user_row = await self.get_user_by_telegram_id(conn, telegram_id)

            # Handle referral only for NEW users
            if is_new and user_data.ref_code and user_row:
                from app.services.referral_service import ReferralService
                await ReferralService().process_referral_on_user_upsert(conn, user_row.id, user_data.ref_code)
            
            # Commit the transaction that was auto-started by db_conn's set_config
            await conn.commit()
            return user_row
        except Exception:
            await conn.rollback()
            raise