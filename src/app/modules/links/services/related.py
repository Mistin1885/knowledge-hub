import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, User
from app.modules.links.infra import repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.services import policy

LINK_WEIGHT = 3.0
TAG_WEIGHT = 1.0
SEMANTIC_WEIGHT = 4.0


async def related_pages(
    s: AsyncSession, user: User, page_id: uuid.UUID, limit: int = 10
) -> list[dict]:
    """Blend of direct links, shared tags, and embedding similarity."""
    page = await pages_service.get_for_read(s, user, page_id)
    scores: dict[uuid.UUID, float] = {}
    reasons: dict[uuid.UUID, set[str]] = {}

    def bump(other_id: uuid.UUID, amount: float, reason: str):
        scores[other_id] = scores.get(other_id, 0.0) + amount
        reasons.setdefault(other_id, set()).add(reason)

    for other_id in await repo.neighbor_ids(s, page.id):
        bump(other_id, LINK_WEIGHT, "links")
    for other_id, shared in (await repo.pages_sharing_tags(s, page.id)).items():
        bump(other_id, TAG_WEIGHT * min(shared, 3), "tags")

    if page.embedding is not None:
        distance = Page.embedding.cosine_distance(page.embedding)
        rows = await s.execute(
            select(Page.id, distance)
            .where(
                Page.workspace_id == page.workspace_id,
                Page.id != page.id,
                Page.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit * 3)
        )
        for other_id, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity > 0.3:
                bump(other_id, SEMANTIC_WEIGHT * similarity, "semantic")

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    results: list[dict] = []
    for other_id, score in ranked:
        if len(results) >= limit:
            break
        other = await s.get(Page, other_id)
        if other is None or other.workspace_id != page.workspace_id:
            continue
        if await policy.can_read_page(s, user, other):
            results.append({"page": other, "score": round(score, 3), "reasons": sorted(reasons[other_id])})
    return results
