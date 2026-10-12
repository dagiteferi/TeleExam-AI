"""Add app_settings table for configurable key-value settings

Revision ID: d1e2f3a4b5c6
Revises: 6094c8b5e6c4
Create Date: 2026-10-12 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = '7c2e9a1f4b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    # Seed the default support contact setting
    op.execute(
        """
        INSERT INTO app_settings (key, value, description, is_public, created_at, updated_at)
        VALUES (
            'support_contact_url',
            'https://t.me/your_support_handle',
            'Telegram handle or URL shown as the Contact Support button in the bot',
            TRUE,
            NOW(),
            NOW()
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table('app_settings')
