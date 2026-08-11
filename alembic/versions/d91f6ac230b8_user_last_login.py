"""persist user last login

Revision ID: d91f6ac230b8
Revises: b72f39f65a41
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d91f6ac230b8"
down_revision: str | Sequence[str] | None = "b72f39f65a41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE users
        SET last_login_at = recent.last_login_at
        FROM (
            SELECT user_id, MAX(created_at) AS last_login_at
            FROM sessions
            GROUP BY user_id
        ) AS recent
        WHERE users.id = recent.user_id
        """
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
