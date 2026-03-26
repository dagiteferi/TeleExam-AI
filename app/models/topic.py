from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, Text, ForeignKey, UniqueConstraint # Added UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.course import Course


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)

    course = relationship("Course", backref="topics")

    __table_args__ = (
        UniqueConstraint("course_id", "code", name="uq_topic_course_code"), # Corrected
    )