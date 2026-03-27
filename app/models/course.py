from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)

    department = relationship("Department", backref="courses")

    __table_args__ = (
        UniqueConstraint("department_id", "code", name="uq_course_dept_code"),
    )
