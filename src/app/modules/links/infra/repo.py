import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageLink, PageTag, Tag
from app.modules.links.domain.parser import ParsedLink


async def resolve_title(
    s: AsyncSession, workspace_id: uuid.UUID, title: str
) -> uuid.UUID | None:
    """Resolve a canonical vault path, path alias, or unique basename."""
    from app.modules.pages.services import vault

    node = await vault.resolve_target(s, workspace_id, title)
    return node.id if node else None


async def replace_links(
    s: AsyncSession, source_page: Page, links: list[ParsedLink]
) -> None:
    await s.execute(delete(PageLink).where(PageLink.source_page_id == source_page.id))
    for link in links:
        target_id = await resolve_title(s, source_page.workspace_id, link.target_title)
        if target_id == source_page.id:
            target_id = None if link.target_title.lower() != source_page.title.lower() else target_id
        s.add(
            PageLink(
                source_page_id=source_page.id,
                target_page_id=target_id,
                target_title=link.target_title,
                kind=link.kind,
                context=link.context,
            )
        )
    await s.flush()


async def resolve_pending_links_to(s: AsyncSession, page: Page) -> None:
    """Resolve pending title/path links that now point at ``page``."""
    source_ids = select(Page.id).where(Page.workspace_id == page.workspace_id)
    pending = list(
        await s.scalars(
            select(PageLink).where(
                PageLink.target_page_id.is_(None), PageLink.source_page_id.in_(source_ids)
            )
        )
    )
    for link in pending:
        if await resolve_title(s, page.workspace_id, link.target_title) == page.id:
            link.target_page_id = page.id


async def unresolve_links_to(s: AsyncSession, page_id: uuid.UUID) -> None:
    await s.execute(
        update(PageLink).where(PageLink.target_page_id == page_id).values(target_page_id=None)
    )


async def backlinks(s: AsyncSession, page_id: uuid.UUID) -> list[tuple[Page, str | None]]:
    rows = await s.execute(
        select(Page, PageLink.context)
        .join(PageLink, PageLink.source_page_id == Page.id)
        .where(PageLink.target_page_id == page_id)
        .order_by(Page.updated_at.desc())
    )
    return [(p, c) for p, c in rows]


async def outgoing(s: AsyncSession, page_id: uuid.UUID) -> list[tuple[PageLink, Page | None]]:
    rows = await s.execute(
        select(PageLink, Page)
        .outerjoin(Page, Page.id == PageLink.target_page_id)
        .where(PageLink.source_page_id == page_id)
        .order_by(PageLink.target_title)
    )
    return [(link, page) for link, page in rows]


async def workspace_links(s: AsyncSession, workspace_id: uuid.UUID) -> list[PageLink]:
    source_ids = select(Page.id).where(Page.workspace_id == workspace_id)
    return list(
        await s.scalars(
            select(PageLink).where(
                PageLink.source_page_id.in_(source_ids), PageLink.target_page_id.is_not(None)
            )
        )
    )


async def link_degree(s: AsyncSession, workspace_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """page_id -> resolved in+out link count."""
    source_ids = select(Page.id).where(Page.workspace_id == workspace_id)
    degree: dict[uuid.UUID, int] = {}
    out_rows = await s.execute(
        select(PageLink.source_page_id, func.count())
        .where(PageLink.source_page_id.in_(source_ids), PageLink.target_page_id.is_not(None))
        .group_by(PageLink.source_page_id)
    )
    in_rows = await s.execute(
        select(PageLink.target_page_id, func.count())
        .where(PageLink.target_page_id.in_(source_ids))
        .group_by(PageLink.target_page_id)
    )
    for pid, n in list(out_rows) + list(in_rows):
        degree[pid] = degree.get(pid, 0) + n
    return degree


async def neighbor_ids(s: AsyncSession, page_id: uuid.UUID) -> set[uuid.UUID]:
    """Pages directly linked with this one, either direction."""
    out_ids = await s.scalars(
        select(PageLink.target_page_id).where(
            PageLink.source_page_id == page_id, PageLink.target_page_id.is_not(None)
        )
    )
    in_ids = await s.scalars(
        select(PageLink.source_page_id).where(PageLink.target_page_id == page_id)
    )
    return {i for i in list(out_ids) + list(in_ids) if i != page_id}


async def pages_sharing_tags(s: AsyncSession, page_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """other_page_id -> number of tags shared with `page_id`."""
    my_tags = select(PageTag.tag_id).where(PageTag.page_id == page_id)
    rows = await s.execute(
        select(PageTag.page_id, func.count())
        .where(PageTag.tag_id.in_(my_tags), PageTag.page_id != page_id)
        .group_by(PageTag.page_id)
    )
    return dict(rows.all())


async def workspace_tag_edges(
    s: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    """(page_id, tag_name) pairs for the workspace graph's tag nodes."""
    rows = await s.execute(
        select(PageTag.page_id, Tag.name)
        .join(Tag, Tag.id == PageTag.tag_id)
        .where(Tag.workspace_id == workspace_id)
    )
    return list(rows.all())
