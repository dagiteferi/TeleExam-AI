from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)

    
    role = Column(Text, nullable=False, default="admin")

   
    permissions = Column(ARRAY(Text), nullable=False, server_default="{}")

    
    invited_by_email = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
