"""Chunk + embed a page's content into page_chunks, and refresh the page-level
mean embedding used for related-page similarity."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page
from app.modules.search.domain import chunking
from app.modules.search.infra import embeddings, repo
from app.shared.logging import get_logger
from app.shared.utils import sha256_hex

log = get_logger(__name__)


async def index_page_chunks(s: AsyncSession, page: Page) -> None:
    chunks = chunking.chunk_markdown(page.content_md, page.title)
    hashes = [sha256_hex(chunking.embedding_input(page.title, c.heading, c.text)) for c in chunks]

    vectors: list[list[float] | None] = [None] * len(chunks)
    if embeddings.enabled() and chunks:
        cached = await repo.existing_chunk_embeddings(s, page.id)
        missing = [i for i, h in enumerate(hashes) if h not in cached]
        for i, h in enumerate(hashes):
            if h in cached:
                vectors[i] = list(cached[h])
        if missing:
            fresh = await embeddings.embed_texts(
                [
                    chunking.embedding_input(page.title, chunks[i].heading, chunks[i].text)
                    for i in missing
                ]
            )
            if fresh is not None:
                for i, vec in zip(missing, fresh, strict=True):
                    vectors[i] = vec

    await repo.replace_chunks(s, page.id, chunks, hashes, vectors)

    present = [v for v in vectors if v is not None]
    page.embedding = (
        [sum(dim) / len(present) for dim in zip(*present, strict=True)] if present else None
    )


async def reindex_workspace(s: AsyncSession, workspace_id: uuid.UUID) -> int:
    from sqlalchemy import select

    count = 0
    for page in await s.scalars(select(Page).where(Page.workspace_id == workspace_id)):
        await index_page_chunks(s, page)
        count += 1
    return count
