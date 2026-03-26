from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
