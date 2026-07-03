import uuid

from sqlalchemy import case, delete, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageChunk
from app.modules.search.domain.chunking import Chunk

TS_CONFIG = text("'english'::regconfig")


async def replace_chunks(
    s: AsyncSession,
    page_id: uuid.UUID,
    chunks: list[Chunk],
    hashes: list[str],
    embeddings: list[list[float] | None],
) -> None:
    await s.execute(delete(PageChunk).where(PageChunk.page_id == page_id))
    for chunk, text_hash, embedding in zip(chunks, hashes, embeddings, strict=True):
        s.add(
            PageChunk(
                page_id=page_id,
                ord=chunk.ord,
                heading=chunk.heading,
                text=chunk.text,
                text_hash=text_hash,
                embedding=embedding,
            )
        )
    await s.flush()


async def existing_chunk_embeddings(
    s: AsyncSession, page_id: uuid.UUID
) -> dict[str, list[float]]:
    """text_hash -> embedding, to avoid re-embedding unchanged chunks."""
    rows = await s.execute(
        select(PageChunk.text_hash, PageChunk.embedding).where(
            PageChunk.page_id == page_id, PageChunk.embedding.is_not(None)
        )
    )
    return dict(rows.all())


def fulltext_rank(query: str):
    """(match_filter, rank_expr) combining tsvector FTS and trigram similarity —
    trigram keeps CJK queries working where tsvector tokenization fails."""
    tsq = func.plainto_tsquery(TS_CONFIG, query)
    tsv = func.to_tsvector(TS_CONFIG, Page.search_text)
    similarity = func.similarity(Page.search_text, query)
    title_hit = Page.title.ilike(f"%{query}%")
    match = or_(
        tsv.op("@@")(tsq),
        Page.search_text.ilike(f"%{query}%"),
        title_hit,
    )
    rank = (
        func.coalesce(func.ts_rank(tsv, tsq), 0.0) * literal(2.0)
        + func.coalesce(similarity, 0.0)
        + case((title_hit, literal(1.5)), else_=literal(0.0))
    )
    return match, rank


async def semantic_chunks(
    s: AsyncSession,
    workspace_id: uuid.UUID,
    query_vector: list[float],
    limit: int,
    page_filter=None,
) -> list[tuple[PageChunk, Page, float]]:
    distance = PageChunk.embedding.cosine_distance(query_vector)
    q = (
        select(PageChunk, Page, distance)
        .join(Page, Page.id == PageChunk.page_id)
        .where(Page.workspace_id == workspace_id, PageChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    if page_filter is not None:
        q = q.where(page_filter)
    rows = await s.execute(q)
    return [(chunk, page, 1.0 - float(dist)) for chunk, page, dist in rows]


async def chunks_for_pages(
    s: AsyncSession, page_ids: list[uuid.UUID], query: str, per_page: int = 2
) -> dict[uuid.UUID, list[PageChunk]]:
    """Best-matching chunks per page for snippet display (trigram ranked)."""
    if not page_ids:
        return {}
    similarity = func.similarity(PageChunk.text, query)
    rows = await s.execute(
        select(PageChunk)
        .where(PageChunk.page_id.in_(page_ids), PageChunk.text.ilike(f"%{query}%"))
        .order_by(similarity.desc())
        .limit(per_page * len(page_ids))
    )
    result: dict[uuid.UUID, list[PageChunk]] = {}
    for chunk in rows.scalars():
        bucket = result.setdefault(chunk.page_id, [])
        if len(bucket) < per_page:
            bucket.append(chunk)
    return result
