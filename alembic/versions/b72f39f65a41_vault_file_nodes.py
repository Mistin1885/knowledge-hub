"""vault file nodes

Revision ID: b72f39f65a41
Revises: a1c3f0d21b7e
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b72f39f65a41"
down_revision: str | Sequence[str] | None = "a1c3f0d21b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "page_links", "target_title", existing_type=sa.String(length=500), type_=sa.String(length=2000)
    )
    op.add_column(
        "pages",
        sa.Column("node_type", sa.String(length=16), server_default="markdown", nullable=False),
    )
    op.execute("UPDATE pages SET node_type = 'folder' WHERE is_folder IS TRUE")
    op.create_index("ix_pages_node_type", "pages", ["node_type"], unique=False)

    op.create_table(
        "file_assets",
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("disk_path", sa.String(length=500), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("legacy_attachment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("node_id"),
    )
    op.create_index(
        "ix_file_assets_legacy_attachment_id",
        "file_assets",
        ["legacy_attachment_id"],
        unique=True,
    )

    op.create_table(
        "node_aliases",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=2000), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "path"),
    )
    op.create_index("ix_node_aliases_node_id", "node_aliases", ["node_id"], unique=False)
    op.create_index(
        "ix_node_aliases_workspace_id", "node_aliases", ["workspace_id"], unique=False
    )

    # Materialise every legacy attachment as a file node below its owning
    # page. The payload remains in place and legacy URLs continue to resolve.
    op.execute(
        """
        WITH ranked_attachments AS (
            SELECT
                a.*,
                ROW_NUMBER() OVER (
                    PARTITION BY a.page_id, lower(a.filename)
                    ORDER BY a.created_at, a.id
                ) + CASE WHEN EXISTS (
                    SELECT 1
                    FROM pages existing_child
                    WHERE existing_child.parent_id = a.page_id
                      AND lower(existing_child.title) = lower(a.filename)
                ) THEN 1 ELSE 0 END AS duplicate_rank
            FROM attachments a
        )
        INSERT INTO pages (
            id, workspace_id, parent_id, title, icon, content_md, status,
            visibility, is_folder, node_type, position, version, owner_id,
            created_by, updated_by, search_text, embedding, created_at, updated_at
        )
        SELECT
            a.id, a.workspace_id, a.page_id,
            CASE
                WHEN a.duplicate_rank = 1 THEN a.filename
                WHEN a.filename ~ '\\.[^.]+$' THEN regexp_replace(
                    a.filename,
                    '(\\.[^.]+)$',
                    ' (' || a.duplicate_rank || ')\\1'
                )
                ELSE a.filename || ' (' || a.duplicate_rank || ')'
            END,
            NULL, '', 'published',
            p.visibility, FALSE, 'file',
            COALESCE((SELECT MAX(s.position) FROM pages s WHERE s.parent_id = a.page_id), 0)
                + ROW_NUMBER() OVER (PARTITION BY a.page_id ORDER BY a.created_at, a.id),
            0, p.owner_id, a.created_by, a.created_by,
            CASE
                WHEN a.duplicate_rank = 1 THEN a.filename
                WHEN a.filename ~ '\\.[^.]+$' THEN regexp_replace(
                    a.filename,
                    '(\\.[^.]+)$',
                    ' (' || a.duplicate_rank || ')\\1'
                )
                ELSE a.filename || ' (' || a.duplicate_rank || ')'
            END,
            NULL,
            a.created_at, a.created_at
        FROM ranked_attachments a
        JOIN pages p ON p.id = a.page_id
        WHERE NOT EXISTS (SELECT 1 FROM pages existing WHERE existing.id = a.id)
        """
    )
    op.execute(
        """
        INSERT INTO file_assets (
            node_id, content_type, size, disk_path, checksum_sha256, legacy_attachment_id
        )
        SELECT a.id, a.content_type, a.size, a.disk_path, NULL, a.id
        FROM attachments a
        JOIN pages p ON p.id = a.id AND p.node_type = 'file'
        """
    )
    op.execute(
        """
        INSERT INTO page_shares (page_id, user_id, created_at)
        SELECT a.id, shared.user_id, shared.created_at
        FROM attachments a
        JOIN pages file_node ON file_node.id = a.id AND file_node.node_type = 'file'
        JOIN page_shares shared ON shared.page_id = a.page_id
        ON CONFLICT (page_id, user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_node_aliases_workspace_id", table_name="node_aliases")
    op.drop_index("ix_node_aliases_node_id", table_name="node_aliases")
    op.drop_table("node_aliases")
    op.drop_index("ix_file_assets_legacy_attachment_id", table_name="file_assets")
    op.drop_table("file_assets")
    op.execute("DELETE FROM pages WHERE node_type = 'file'")
    op.drop_index("ix_pages_node_type", table_name="pages")
    op.drop_column("pages", "node_type")
    op.alter_column(
        "page_links", "target_title", existing_type=sa.String(length=2000), type_=sa.String(length=500)
    )
