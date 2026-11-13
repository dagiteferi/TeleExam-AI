"""let admins edit and delete announcements after sending

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New nullable / defaulted columns only: existing rows keep working.
    # version goes up on every edit; deleted_at is set when the admin deletes it.
    op.add_column("announcements", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("announcements", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    # Telegram message id of the delivered copy (needed to edit / delete it in the user's chat)
    # and which version of the text that copy currently shows.
    op.add_column("announcement_deliveries", sa.Column("message_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "announcement_deliveries", sa.Column("text_version", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade() -> None:
    op.drop_column("announcement_deliveries", "text_version")
    op.drop_column("announcement_deliveries", "message_id")
    op.drop_column("announcements", "deleted_at")
    op.drop_column("announcements", "version")
