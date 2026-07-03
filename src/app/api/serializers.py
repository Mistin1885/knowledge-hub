"""ORM -> response-schema assembly shared by routers and the MCP server."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.pages import PageDetailOut, PageOut
from app.infra.db.models import Page, User
from app.modules.links.services import links as links_service
from app.modules.pages.infra import repo as pages_repo


async def page_out(s: AsyncSession, page: Page) -> PageOut:
    # explicit fetch instead of the lazy relationship: pages arrive here from
    # arbitrary queries and lazy-loading is unavailable under asyncio
    owner = await s.get(User, page.owner_id) if page.owner_id else None
    return PageOut(
        id=page.id,
        workspace_id=page.workspace_id,
        parent_id=page.parent_id,
        title=page.title,
        icon=page.icon,
        status=page.status,
        visibility=page.visibility,
        position=page.position,
        is_folder=page.is_folder,
        owner={"id": owner.id, "name": owner.name} if owner else None,
        tags=await pages_repo.get_page_tags(s, page.id),
        metadata=await pages_repo.get_page_metadata(s, page.id),
        created_by=page.created_by,
        updated_by=page.updated_by,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


async def page_detail_out(s: AsyncSession, page: Page) -> PageDetailOut:
    base = await page_out(s, page)
    inbound, outbound = await links_service.count_links(s, page.id)
    return PageDetailOut(
        **base.model_dump(),
        content_md=page.content_md,
        backlink_count=inbound,
        outgoing_count=outbound,
    )
