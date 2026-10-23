"""Hash plain-text admin passwords in admin_users.password_hash

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-23 10:00:00.000000

"""
import base64
import hashlib
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Same format as app.core.security.hash_password, inlined so the migration
# doesn't depend on app code: scrypt$n$r$p$salt$hash (base64 parts).
def _hash_password(password: str) -> str:
    n, r, p = 2**14, 8, 1
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()
    return f"scrypt${n}${r}${p}${b64(salt)}${b64(digest)}"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, password_hash FROM admin_users")).fetchall()
    for admin_id, stored in rows:
        if stored and not stored.startswith("scrypt$"):
            conn.execute(
                sa.text("UPDATE admin_users SET password_hash = :h WHERE id = :id"),
                {"h": _hash_password(stored), "id": admin_id},
            )


def downgrade() -> None:
    # Hashing is one-way: plain-text passwords can't be restored.
    pass
