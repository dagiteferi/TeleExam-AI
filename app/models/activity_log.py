from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.user import User


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)
    event_name = Column(Text, nullable=False)
    event_ts = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    properties = Column(JSONB, nullable=False, default={})

    user = relationship("User", backref="activity_logs")
