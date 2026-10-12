from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.db.postgres import Base


class AppSetting(Base):
    """
    Key-value store for configurable application settings managed via the admin portal.
    Examples: support_contact_url, pro_price_etb, etc.
    """
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False)  # expose via /api/public/settings

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
