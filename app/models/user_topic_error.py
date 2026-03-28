from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.user import User
from app.models.topic import Topic


class UserTopicError(Base):
    __tablename__ = "user_topic_errors"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True)
    error_count = Column(Integer, nullable=False, default=0)
    last_error_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)

    user = relationship("User", backref="user_topic_errors")
    topic = relationship("Topic", backref="user_topic_errors")
