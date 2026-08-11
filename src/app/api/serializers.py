"""ORM -> response-schema assembly shared by routers and the MCP server."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.pages import PageDetailOut, PageOut, VaultTreeNodeOut
from app.infra.db.models import Page, User
from app.modules.links.services import links as links_service
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import vault


async def page_out(
    s: AsyncSession, page: Page, *, file_count: int | None = None
) -> PageOut:
    # explicit fetch instead of the lazy relationship: pages arrive here from
    # arbitrary queries and lazy-loading is unavailable under asyncio
    owner = await s.get(User, page.owner_id) if page.owner_id else None
    asset = await pages_repo.get_file_asset(s, page.id) if page.node_type == "file" else None
    preview_kind = vault.preview_kind_for_content_type(asset.content_type) if asset else None
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
        node_type=page.node_type,
        owner={"id": owner.id, "name": owner.name} if owner else None,
        tags=await pages_repo.get_page_tags(s, page.id),
        metadata=await pages_repo.get_page_metadata(s, page.id),
        created_by=page.created_by,
        updated_by=page.updated_by,
        created_at=page.created_at,
        updated_at=page.updated_at,
        content_type=asset.content_type if asset else None,
        size=asset.size if asset else None,
        preview_kind=preview_kind,
        preview_url=f"/api/v1/files/{page.id}/preview" if preview_kind else None,
        download_url=f"/api/v1/files/{page.id}/download" if asset else None,
        file_count=file_count if page.node_type == "folder" or page.is_folder else None,
    )


async def pages_out(
    s: AsyncSession, pages: list[Page], *, file_counts: dict | None = None
) -> list[PageOut]:
    """Serialize a page collection with three bulk lookups instead of N+1 queries."""
    node_ids = [page.id for page in pages]
    assets = {
        asset.node_id: asset for asset in await pages_repo.file_assets_for_nodes(s, node_ids)
    }
    tags = await pages_repo.page_tags_for_nodes(s, node_ids)
    metadata = await pages_repo.page_metadata_for_nodes(s, node_ids)
    result: list[PageOut] = []
    for page in pages:
        asset = assets.get(page.id)
        preview_kind = vault.preview_kind_for_content_type(asset.content_type) if asset else None
        owner = page.owner
        result.append(
            PageOut(
                id=page.id,
                workspace_id=page.workspace_id,
                parent_id=page.parent_id,
                title=page.title,
                icon=page.icon,
                status=page.status,
                visibility=page.visibility,
                position=page.position,
                is_folder=page.is_folder,
                node_type=page.node_type,
                owner={"id": owner.id, "name": owner.name} if owner else None,
                tags=tags.get(page.id, []),
                metadata=metadata.get(page.id, {}),
                created_by=page.created_by,
                updated_by=page.updated_by,
                created_at=page.created_at,
                updated_at=page.updated_at,
                content_type=asset.content_type if asset else None,
                size=asset.size if asset else None,
                preview_kind=preview_kind,
                preview_url=f"/api/v1/files/{page.id}/preview" if preview_kind else None,
                download_url=f"/api/v1/files/{page.id}/download" if asset else None,
                file_count=(file_counts or {}).get(page.id)
                if page.node_type == "folder" or page.is_folder
                else None,
            )
        )
    return result


async def vault_tree_nodes_out(
    s: AsyncSession,
    pages: list[Page],
    *,
    file_counts: dict,
    parents_with_children: set,
    parent_overrides: dict | None = None,
) -> list[VaultTreeNodeOut]:
    assets = {
        asset.node_id: asset
        for asset in await pages_repo.file_assets_for_nodes(s, [page.id for page in pages])
    }
    return [
        VaultTreeNodeOut(
            id=page.id,
            workspace_id=page.workspace_id,
            parent_id=(parent_overrides or {}).get(page.id, page.parent_id),
            title=page.title,
            icon=page.icon,
            status=page.status,
            visibility=page.visibility,
            position=page.position,
            is_folder=page.is_folder,
            node_type=page.node_type,
            preview_kind=(
                vault.preview_kind_for_content_type(assets[page.id].content_type)
                if page.id in assets
                else None
            ),
            file_count=file_counts.get(page.id)
            if page.node_type == "folder" or page.is_folder
            else None,
            has_children=page.id in parents_with_children,
        )
        for page in pages
    ]


async def page_detail_out(s: AsyncSession, page: Page) -> PageDetailOut:
    base = await page_out(s, page)
    inbound, outbound = await links_service.count_links(s, page.id)
    return PageDetailOut(
        **base.model_dump(),
        content_md=page.content_md,
        backlink_count=inbound,
        outgoing_count=outbound,
    )
