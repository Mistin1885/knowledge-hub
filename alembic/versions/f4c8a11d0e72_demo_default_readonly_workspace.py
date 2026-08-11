"""rename engineering workspace and normalize demo access

Revision ID: f4c8a11d0e72
Revises: d91f6ac230b8
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4c8a11d0e72"
down_revision: str | Sequence[str] | None = "d91f6ac230b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This deployment's shared Engineering workspace becomes the public demo.
    op.execute(
        """
        UPDATE workspaces
        SET name = 'demo', slug = 'demo', updated_at = now()
        WHERE slug = 'engineering'
        """
    )
    # Keep every owner intact; all other existing users are read-only members.
    op.execute(
        """
        INSERT INTO workspace_members (workspace_id, user_id, role, joined_at)
        SELECT workspaces.id, users.id, 'viewer', now()
        FROM workspaces
        CROSS JOIN users
        WHERE workspaces.slug = 'demo'
        ON CONFLICT (workspace_id, user_id) DO UPDATE
        SET role = 'viewer'
        WHERE workspace_members.role <> 'owner'
        """
    )


def downgrade() -> None:
    # Membership roles cannot be reconstructed after normalization.
    op.execute(
        """
        UPDATE workspaces
        SET name = 'Engineering', slug = 'engineering', updated_at = now()
        WHERE slug = 'demo'
        """
    )
