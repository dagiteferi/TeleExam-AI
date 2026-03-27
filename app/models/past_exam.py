from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, Text, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base

class PastExam(Base):
    __tablename__ = "past_exams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True) 
    year = Column(Integer, nullable=False)
    semester = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)

    department = relationship("Department", backref="past_exams")
    course = relationship("Course", backref="past_exams")
    
    __table_args__ = (
        UniqueConstraint("department_id", "course_id", "year", "semester", name="uq_past_exam_dept_yr_sem"),
    )


class PastExamQuestion(Base):
    __tablename__ = "past_exam_questions"

    past_exam_id = Column(UUID(as_uuid=True), ForeignKey("past_exams.id"), primary_key=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), primary_key=True)
