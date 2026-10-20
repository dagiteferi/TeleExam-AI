"""add active department for dual-degree switching

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL means "studying the main department".
    op.add_column("users", sa.Column("active_department_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_department_id",
        "users",
        "departments",
        ["active_department_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_active_department_id", "users", type_="foreignkey")
    op.drop_column("users", "active_department_id")
