"""add dual department support

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-10-20 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("secondary_department_id", sa.UUID(), nullable=True))
    op.add_column("users", sa.Column("secondary_department_unlocked", sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET secondary_department_unlocked = FALSE WHERE secondary_department_unlocked IS NULL")
    op.alter_column("users", "secondary_department_unlocked", nullable=False)
    op.create_foreign_key(
        "fk_users_secondary_department_id",
        "users",
        "departments",
        ["secondary_department_id"],
        ["id"],
    )

    op.add_column(
        "payment_requests",
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="pro"),
    )
    op.add_column("payment_requests", sa.Column("target_department_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_payment_requests_target_department_id",
        "payment_requests",
        "departments",
        ["target_department_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_payment_requests_target_department_id", "payment_requests", type_="foreignkey")
    op.drop_column("payment_requests", "target_department_id")
    op.drop_column("payment_requests", "kind")
    op.drop_constraint("fk_users_secondary_department_id", "users", type_="foreignkey")
    op.drop_column("users", "secondary_department_unlocked")
    op.drop_column("users", "secondary_department_id")
