from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Column, DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    screenshot_url = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected
    
    # Track which admin approved or rejected it
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # Relationships
    user = relationship("User")
    admin = relationship("AdminUser")
