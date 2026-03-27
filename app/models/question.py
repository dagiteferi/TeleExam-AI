from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Text, ForeignKey, CHAR, SmallInteger, LargeBinary, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.course import Course
from app.models.topic import Topic


class QuestionFormat(str, Enum):
    mcq = "mcq"


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    format = Column(Enum(enum_class=QuestionFormat, name='question_format_enum'), nullable=False, default=QuestionFormat.mcq)

    prompt = Column(Text, nullable=False)
    choice_a = Column(Text, nullable=False)
    choice_b = Column(Text, nullable=False)
    choice_c = Column(Text, nullable=False)
    choice_d = Column(Text, nullable=False)
    correct_choice = Column(CHAR(1), nullable=False) # CHECK (correct_choice IN ('A','B','C','D'))

    difficulty = Column(SmallInteger, nullable=True) # CHECK (difficulty BETWEEN 1 AND 5)
    source = Column(Text, nullable=True)

    explanation_static = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    content_hash = Column(LargeBinary, nullable=False, unique=True) # idempotent ingestion guard
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    course = relationship("Course", backref="questions")
    topic = relationship("Topic", backref="questions")

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_question_content_hash"),
    )
