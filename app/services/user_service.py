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

        if existing_user:
            # Update existing user
            update_data = user_data.model_dump(exclude_unset=True)
            if 'ref_code' in update_data:
                del update_data['ref_code'] # ref_code is only for initial creation

            if update_data:
                stmt = update(User).where(User.telegram_id == telegram_id).values(**update_data).returning(User)
                result = await conn.execute(stmt)
                user = result.scalar_one()
            else:
                user = existing_user
        else:
            # Create new user
            insert_data = user_data.model_dump()
            if insert_data.get('ref_code'):
                # Logic to find invited_by_user_id from ref_code
                # For now, let's assume ref_code is directly the invited_by_user_id for simplicity or handle it later
                # This part needs to be properly implemented based on referral system design
                # For now, we'll just pass it if it's a valid UUID, otherwise ignore
                try:
                    invited_by_uuid = uuid.UUID(str(insert_data['ref_code']))
                    insert_data['invited_by_user_id'] = invited_by_uuid
                except ValueError:
                    pass # Invalid ref_code, ignore
                del insert_data['ref_code']

            stmt = insert(User).values(**insert_data).returning(User)
            result = await conn.execute(stmt)
            user = result.scalar_one()

        await conn.commit()
        return user