"""add_banned_until_to_users

Revision ID: 7c2e9a1f4b3d
Revises: 6094c8b5e6c4
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c2e9a1f4b3d'
down_revision: Union[str, None] = '6094c8b5e6c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = permanent ban (when is_banned is true); a timestamp = ban ends at that time
    op.add_column('users', sa.Column('banned_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'banned_until')
