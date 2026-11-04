"""Index user_answers by user for progress, weak topics and Review My Mistakes

Revision ID: e5f6a7b8c9d0
Revises: a1b2c3d4e5f7
Create Date: 2026-11-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'  # after add_can_record_to_users
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every My Progress load reads one user's answers (per-course stats, weak topics,
    # open mistakes). Without this index each of those scans the whole table.
    op.create_index(
        'ix_user_answers_user_id_answered_at',
        'user_answers',
        ['user_id', 'answered_at'],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ix_user_answers_user_id_answered_at', table_name='user_answers', if_exists=True)
