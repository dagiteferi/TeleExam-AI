from __future__ import annotations

import datetime
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Announcement(Base):
    """A message an admin sent to a group of users (all, PRO, free, dual, a department or one user)."""

    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    audience = Column(String(30), nullable=False)  # all, pro, free, dual, department, user
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Bot that delivers it (from TELEGRAM_BOT_TOKEN). Local and production share one
    # database, so each backend only queues and lists its own bot's announcements.
    bot_id = Column(BigInteger, nullable=True, index=True)
    created_by = Column(String(255), nullable=True)  # admin email
    recipient_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)


class AnnouncementDelivery(Base):
    """
    One recipient of an announcement. The bot sends pending deliveries in the
    background and skips users who are busy (in an exam, AI chat, ...) until they are idle.
    """

    __tablename__ = "announcement_deliveries"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_announcement_delivery_user"),
        Index("ix_announcement_deliveries_status_attempt", "status", "last_attempt_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id = Column(UUID(as_uuid=True), ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, sent, failed, cancelled
    error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
