from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, Text, ForeignKey, Integer, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.user import User
from app.models.course import Course
from app.models.topic import Topic
from app.models.exam_template import ExamTemplate


class SessionMode(str, Enum):
    exam = "exam"
    practice = "practice"
    quiz = "quiz"


class ExamResult(Base):
    __tablename__ = "exam_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    mode = Column(Enum(SessionMode), nullable=False)
    exam_template_id = Column(UUID(as_uuid=True), ForeignKey("exam_templates.id"), nullable=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)

    question_count = Column(Integer, nullable=False)
    correct_count = Column(Integer, nullable=False)
    wrong_count = Column(Integer, nullable=False)
    score_percent = Column(Numeric(5, 2), nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Integer, nullable=False)

    metadata_ = Column(JSONB, nullable=False, default={}) # Renamed to metadata_ to avoid conflict with Python keyword
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)

    user = relationship("User", backref="exam_results")
    course = relationship("Course", backref="exam_results")
    topic = relationship("Topic", backref="exam_results")
    exam_template = relationship("ExamTemplate", backref="exam_results")
