"""chunk-level fts

Move fulltext matching from pages.search_text to page_chunks.text so huge
documents never hit PostgreSQL's 1 MB tsvector limit on write.

Downgrade caveat: recreating ix_pages_fts fails if any page's search_text
already exceeds the tsvector limit — trim those pages first.

Revision ID: a1c3f0d21b7e
Revises: eca98eacb3d9
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c3f0d21b7e'
down_revision: Union[str, Sequence[str], None] = 'eca98eacb3d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create the replacement index before dropping the old one so search is
    # never without an index if this migration fails midway
    op.create_index(
        'ix_page_chunks_fts',
        'page_chunks',
        [sa.literal_column("to_tsvector('english'::regconfig, text)")],
        unique=False,
        postgresql_using='gin',
    )
    op.drop_index('ix_pages_fts', table_name='pages', postgresql_using='gin')


def downgrade() -> None:
    op.create_index(
        'ix_pages_fts',
        'pages',
        [sa.literal_column("to_tsvector('english'::regconfig, search_text)")],
        unique=False,
        postgresql_using='gin',
    )
    op.drop_index('ix_page_chunks_fts', table_name='page_chunks', postgresql_using='gin')
