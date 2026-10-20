"""add announcements and their per-user deliveries

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New tables only: existing tables and data are not touched.
    op.create_table(
        "announcements",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=30), nullable=False),
        sa.Column("department_id", sa.UUID(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Bot that delivers it (from the backend's TELEGRAM_BOT_TOKEN). Local and production
        # share this database, so each backend only handles its own bot's announcements.
        sa.Column("bot_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "announcement_deliveries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("announcement_id", sa.UUID(), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_delivery_user"),
    )
    op.create_index(
        "ix_announcement_deliveries_status_attempt",
        "announcement_deliveries",
        ["status", "last_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_announcement_deliveries_status_attempt", table_name="announcement_deliveries")
    op.drop_table("announcement_deliveries")
    op.drop_table("announcements")
