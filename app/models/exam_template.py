from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Text, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.course import Course
from app.models.topic import Topic


class ExamTemplate(Base):
    __tablename__ = "exam_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    mode = Column(Text, nullable=False) # CHECK (mode IN ('exam','quiz'))
    question_count = Column(Integer, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)

    course = relationship("Course", backref="exam_templates")
    topics = relationship("ExamTemplateTopic", back_populates="exam_template")

    __table_args__ = (
        UniqueConstraint("course_id", "code", name="uq_exam_template_course_code"),
    )


class ExamTemplateTopic(Base):
    __tablename__ = "exam_template_topics"

    exam_template_id = Column(UUID(as_uuid=True), ForeignKey("exam_templates.id"), primary_key=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True)
    weight = Column(Numeric(6, 3), nullable=False, default=1.0)

    exam_template = relationship("ExamTemplate", back_populates="topics")
    topic = relationship("Topic")
