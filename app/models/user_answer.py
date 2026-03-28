from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, CHAR, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base
from app.models.exam_result import ExamResult
from app.models.user import User
from app.models.question import Question
from app.models.topic import Topic


class UserAnswer(Base):
    __tablename__ = "user_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_result_id = Column(UUID(as_uuid=True), ForeignKey("exam_results.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)

    selected_choice = Column(CHAR(1), nullable=False) # CHECK (selected_choice IN ('A','B','C','D'))
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=False)

    exam_result = relationship("ExamResult", backref="user_answers")
    user = relationship("User", backref="user_answers")
    question = relationship("Question", backref="user_answers")
    topic = relationship("Topic", backref="user_answers")

    __table_args__ = (
        UniqueConstraint("exam_result_id", "question_id", name="uq_user_answer_exam_question"),
    )
