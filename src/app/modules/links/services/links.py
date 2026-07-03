import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageLink, User
from app.modules.links.domain import parser
from app.modules.links.infra import repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.services import policy


async def backlinks(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[dict]:
    page = await pages_service.get_for_read(s, user, page_id)
    results = []
    for source, context in await repo.backlinks(s, page.id):
        if await policy.can_read_page(s, user, source):
            results.append({"page": source, "context": context})
    return results


async def outgoing(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[dict]:
    page = await pages_service.get_for_read(s, user, page_id)
    results = []
    for link, target in await repo.outgoing(s, page.id):
        if target is not None and not await policy.can_read_page(s, user, target):
            target = None  # hide private targets, keep the title
        results.append(
            {
                "page": target,
                "target_title": link.target_title,
                "resolved": link.target_page_id is not None,
                "context": link.context,
            }
        )
    return results


async def unlinked_mentions(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[dict]:
    """Pages whose text mentions this page's title without linking to it."""
    page = await pages_service.get_for_read(s, user, page_id)
    if len(page.title.strip()) < 2:
        return []
    linked_sources = select(PageLink.source_page_id).where(PageLink.target_page_id == page.id)
    candidates = await s.scalars(
        select(Page)
        .where(
            Page.workspace_id == page.workspace_id,
            Page.id != page.id,
            Page.id.not_in(linked_sources),
            Page.search_text.ilike(f"%{page.title}%"),
            policy.visible_pages_filter(user.id),
        )
        .order_by(Page.updated_at.desc())
        .limit(50)
    )
    results = []
    for candidate in candidates:
        context = parser.find_unlinked_context(candidate.content_md, page.title)
        if context:
            results.append({"page": candidate, "context": context})
    return results


async def orphans(s: AsyncSession, user: User, workspace_id: uuid.UUID) -> list[Page]:
    from app.shared.constants import Role

    await policy.require_role(s, user, workspace_id, Role.VIEWER)
    linked_as_source = select(PageLink.source_page_id)
    linked_as_target = select(PageLink.target_page_id).where(PageLink.target_page_id.is_not(None))
    return list(
        await s.scalars(
            select(Page)
            .where(
                Page.workspace_id == workspace_id,
                Page.is_folder.is_(False),
                Page.id.not_in(linked_as_source),
                Page.id.not_in(linked_as_target),
                policy.visible_pages_filter(user.id),
            )
            .order_by(Page.updated_at.desc())
        )
    )


async def resolve_title_to_page(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, title: str
) -> Page | None:
    from app.shared.constants import Role

    await policy.require_role(s, user, workspace_id, Role.VIEWER)
    page_id = await repo.resolve_title(s, workspace_id, title)
    if page_id is None:
        return None
    page = await s.get(Page, page_id)
    if page is not None and await policy.can_read_page(s, user, page):
        return page
    return None


async def count_links(s: AsyncSession, page_id: uuid.UUID) -> tuple[int, int]:
    inbound = (
        await s.scalar(
            select(func.count()).where(PageLink.target_page_id == page_id)
        )
    ) or 0
    outbound = (
        await s.scalar(select(func.count()).where(PageLink.source_page_id == page_id))
    ) or 0
    return inbound, outbound
