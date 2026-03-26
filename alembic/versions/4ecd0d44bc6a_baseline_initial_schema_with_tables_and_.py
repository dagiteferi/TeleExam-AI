"""baseline: initial schema with tables and rls

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """This is a baseline migration.
    All tables, indexes and RLS policies were already applied manually via schema.sql.
    Future migrations will add/alter tables from here.
    """
    # No operations needed for baseline (schema already exists)
    pass


def downgrade() -> None:
    """We do not drop tables in downgrade for safety in production."""
    pass