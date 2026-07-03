import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageMetadata, User
from app.modules.pages.infra import repo as pages_repo
from app.modules.search.infra import embeddings, repo
from app.modules.workspaces.services import policy
from app.shared.constants import Permission


async def _apply_filters(
    s: AsyncSession,
    q,
    workspace_id: uuid.UUID,
    tags: list[str],
    status: str | None,
    owner_id: uuid.UUID | None,
    metadata: dict[str, str],
):
    if status:
        q = q.where(Page.status == status)
    if owner_id:
        q = q.where(Page.owner_id == owner_id)
    for tag in tags:
        ids = await pages_repo.page_ids_with_tag(s, workspace_id, tag)
        q = q.where(Page.id.in_(ids or [uuid.UUID(int=0)]))
    for key, value in metadata.items():
        sub = select(PageMetadata.page_id).where(
            PageMetadata.key == key, PageMetadata.value == value
        )
        q = q.where(Page.id.in_(sub))
    return q


async def search(
    s: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    query: str,
    *,
    tags: list[str] | None = None,
    status: str | None = None,
    owner_id: uuid.UUID | None = None,
    metadata: dict[str, str] | None = None,
    mode: str = "hybrid",
    limit: int = 20,
) -> dict:
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    tags, metadata = tags or [], metadata or {}
    query = query.strip()

    semantic_available = embeddings.enabled()
    mode_used = mode if mode != "semantic" or semantic_available else "fulltext"
    if mode == "hybrid" and not semantic_available:
        mode_used = "fulltext"

    scores: dict[uuid.UUID, float] = {}
    pages: dict[uuid.UUID, Page] = {}
    semantic_snippets: dict[uuid.UUID, list[dict]] = {}

    # --- keyword leg ---
    if query and mode_used in ("hybrid", "fulltext"):
        match, rank = repo.fulltext_rank(query)
        q = (
            select(Page, rank)
            .where(Page.workspace_id == workspace_id, match, policy.visible_pages_filter(user.id))
            .order_by(rank.desc())
            .limit(limit * 2)
        )
        q = await _apply_filters(s, q, workspace_id, tags, status, owner_id, metadata)
        for page, r in await s.execute(q):
            pages[page.id] = page
            scores[page.id] = scores.get(page.id, 0.0) + float(r)

    # --- semantic leg ---
    if query and mode_used in ("hybrid", "semantic") and semantic_available:
        vectors = await embeddings.embed_texts([query])
        if vectors:
            hits = await repo.semantic_chunks(
                s, workspace_id, vectors[0], limit * 2, policy.visible_pages_filter(user.id)
            )
            for chunk, page, similarity in hits:
                if similarity < 0.2:
                    continue
                pages[page.id] = page
                scores[page.id] = scores.get(page.id, 0.0) + similarity * 3.0
                semantic_snippets.setdefault(page.id, []).append(
                    {"text": chunk.text[:400], "heading": chunk.heading}
                )
        elif mode == "semantic":
            mode_used = "fulltext"

    # --- filter-only browse (no query) ---
    if not query:
        q = (
            select(Page)
            .where(Page.workspace_id == workspace_id, policy.visible_pages_filter(user.id))
            .order_by(Page.updated_at.desc())
            .limit(limit)
        )
        q = await _apply_filters(s, q, workspace_id, tags, status, owner_id, metadata)
        for page in await s.scalars(q):
            pages[page.id] = page
            scores[page.id] = 0.0

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    keyword_snippets = await repo.chunks_for_pages(s, [pid for pid, _ in ranked], query) if query else {}

    results = []
    for page_id, score in ranked:
        page = pages[page_id]
        snippets = semantic_snippets.get(page_id) or [
            {"text": c.text[:400], "heading": c.heading} for c in keyword_snippets.get(page_id, [])
        ]
        if not snippets and query:
            snippets = [{"text": _fallback_snippet(page, query), "heading": None}]
        results.append({"page": page, "score": round(score, 4), "snippets": snippets[:3]})

    return {"results": results, "mode_used": mode_used}


def _fallback_snippet(page: Page, query: str) -> str:
    text = page.search_text or page.content_md
    idx = text.lower().find(query.lower())
    if idx < 0:
        return text[:200]
    start = max(0, idx - 80)
    return ("…" if start else "") + text[start : idx + 200]


def _keywords(question: str, max_terms: int = 8) -> list[str]:
    """Split a natural-language question into searchable terms: latin words
    plus CJK bigrams (trigram/ILIKE matching needs substrings, not sentences)."""
    import re

    terms: list[str] = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", question)
    for run in re.findall(r"[一-鿿぀-ヿ]{2,}", question):
        if len(run) <= 3:
            terms.append(run)
        else:
            terms.extend(run[i : i + 2] for i in range(len(run) - 1))
    seen: set[str] = set()
    unique = [t for t in terms if not (t.lower() in seen or seen.add(t.lower()))]
    return unique[:max_terms]


async def ask(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, question: str, limit: int = 8
) -> dict:
    """Retrieval with citations: best chunks for a natural-language question."""
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    chunks: list[dict] = []
    seen: set[tuple[uuid.UUID, int]] = set()

    if embeddings.enabled():
        vectors = await embeddings.embed_texts([question])
        if vectors:
            for chunk, page, similarity in await repo.semantic_chunks(
                s, workspace_id, vectors[0], limit, policy.visible_pages_filter(user.id)
            ):
                seen.add((chunk.page_id, chunk.ord))
                chunks.append(
                    {
                        "page": {"id": page.id, "title": page.title},
                        "heading": chunk.heading,
                        "text": chunk.text,
                        "score": round(similarity, 4),
                    }
                )

    if len(chunks) < limit:  # keyword fallback / supplement
        page_hits: dict[uuid.UUID, dict] = {}
        for term in [question, *_keywords(question)]:
            result = await search(s, user, workspace_id, term, mode="fulltext", limit=limit)
            for item in result["results"]:
                hit = page_hits.setdefault(
                    item["page"].id,
                    {"page": item["page"], "score": 0.0, "snippets": []},
                )
                hit["score"] += item["score"]
                hit["snippets"].extend(item["snippets"])
        ranked = sorted(page_hits.values(), key=lambda h: h["score"], reverse=True)
        for hit in ranked:
            for snippet in hit["snippets"][:2]:
                key = (hit["page"].id, hash(snippet["text"]) % 10_000)
                if key not in seen and len(chunks) < limit:
                    seen.add(key)
                    chunks.append(
                        {
                            "page": {"id": hit["page"].id, "title": hit["page"].title},
                            "heading": snippet["heading"],
                            "text": snippet["text"],
                            "score": round(min(hit["score"] / 10.0, 0.99), 4),
                        }
                    )
    return {"chunks": chunks[:limit]}
