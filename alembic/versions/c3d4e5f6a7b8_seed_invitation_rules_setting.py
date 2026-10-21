"""Seed default invitation_rules into app_settings table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-21 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO app_settings (key, value, description, is_public, created_at, updated_at)
        VALUES (
            'invitation_rules',
            '{"free_years": 1, "invites_per_year": 1, "years_per_invite": 1, "invites_to_unlock_all_years": 4, "free_courses_ratio": 0.25, "invites_to_unlock_all_courses": 4, "invites_to_unlock_all": 4, "ai_bonus_per_invite": 0}',
            'Configurable rules for referral invitations: exam years unlocked per invite, free baseline years, courses ratio, and universal unlock threshold.',
            TRUE,
            NOW(),
            NOW()
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'invitation_rules';")
