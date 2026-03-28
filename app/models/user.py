from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB # Added JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(Integer, unique=True, nullable=False)
    telegram_username = Column(Text, nullable=True)
    first_name = Column(Text, nullable=True)
    last_name = Column(Text, nullable=True)

    invite_code = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    invited_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True) # Added ForeignKey
    invite_count = Column(Integer, nullable=False, default=0)
    referral_reward_state = Column(JSONB, nullable=False, default={}) # Added JSONB type and default

    is_pro = Column(Boolean, nullable=False, default=False)
    plan_expiry = Column(DateTime(timezone=True), nullable=True)

    is_banned = Column(Boolean, nullable=False, default=False)
    ban_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now) # Added onupdate

    # Relationships
    invited_by = relationship("User", remote_side=[id], backref="invited_users") # Added relationship
