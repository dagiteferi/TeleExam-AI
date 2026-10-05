from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_name = Column(String(100), nullable=False)
    account_name = Column(String(150), nullable=False)
    account_number = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now)
