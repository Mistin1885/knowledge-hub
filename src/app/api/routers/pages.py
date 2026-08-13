import uuid

from fastapi import APIRouter, Response, status
from fastapi.responses import FileResponse

from app.api import serializers
from app.api.deps import DB, CurrentUser
from app.api.schemas.pages import (
    ChildPageOut,
    MetadataKeyOut,
    PageCreateIn,
    PageDetailOut,
    PageMoveIn,
    PageOut,
    PageUpdateIn,
    ShareIn,
    ShareOut,
    TagOut,
    VaultTreeNodeOut,
    VersionDetailOut,
    VersionOut,
)
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import export as export_service
from app.modules.pages.services import pages as pages_service
from app.modules.pages.services import pdf_export, vault
from app.modules.workspaces.services import policy
from app.orchestration import index_page as pipeline
from app.shared.constants import NodeType, Permission

router = APIRouter(tags=["pages"])


@router.get("/workspaces/{workspace_id}/pages", response_model=list[PageOut])
async def list_pages(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    pages = await pages_service.list_workspace(s, user, workspace_id)
    assets = await pages_repo.file_assets_for_nodes(s, [page.id for page in pages])
    image_node_ids = {asset.node_id for asset in assets if asset.content_type.startswith("image/")}
    counts = pages_repo.folder_file_counts(pages, image_node_ids=image_node_ids)
    return await serializers.pages_out(s, pages, file_counts=counts)


@router.get("/workspaces/{workspace_id}/tree", response_model=list[VaultTreeNodeOut])
async def vault_tree_level(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    s: DB,
    parent_id: uuid.UUID | None = None,
):
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    if parent_id is not None:
        parent = await pages_service.get_for_read(s, user, parent_id)
        if parent.workspace_id != workspace_id or parent.node_type == NodeType.FILE:
            from app.shared.exceptions import NotFoundError

            raise NotFoundError("Folder not found")
    visibility = policy.visible_pages_filter(user.id)
    pages = await pages_repo.list_tree_level(s, workspace_id, parent_id, visibility)
    structure = await pages_repo.tree_structure(s, workspace_id, visibility)
    counts, parents_with_children = pages_repo.folder_file_counts_from_rows(structure)
    visible_ids = {node_id for node_id, *_rest in structure}
    parent_overrides = (
        {
            page.id: None
            for page in pages
            if page.parent_id is not None and page.parent_id not in visible_ids
        }
        if parent_id is None
        else None
    )
    return await serializers.vault_tree_nodes_out(
        s,
        pages,
        file_counts=counts,
        parents_with_children=parents_with_children,
        parent_overrides=parent_overrides,
    )


@router.get("/pages/{page_id}/ancestors", response_model=list[VaultTreeNodeOut])
async def page_ancestors(page_id: uuid.UUID, user: CurrentUser, s: DB):
    page = await pages_service.get_for_read(s, user, page_id)
    ancestors = []
    seen = {page.id}
    parent_id = page.parent_id
    while parent_id is not None and parent_id not in seen:
        seen.add(parent_id)
        parent = await pages_repo.get(s, parent_id)
        if parent is None or not await policy.can_read_page(s, user, parent):
            break
        ancestors.append(parent)
        parent_id = parent.parent_id
    ancestors.reverse()
    visibility = policy.visible_pages_filter(user.id)
    structure = await pages_repo.tree_structure(s, page.workspace_id, visibility)
    counts, parents_with_children = pages_repo.folder_file_counts_from_rows(structure)
    return await serializers.vault_tree_nodes_out(
        s,
        ancestors,
        file_counts=counts,
        parents_with_children=parents_with_children,
    )


@router.post(
    "/workspaces/{workspace_id}/pages",
    response_model=PageDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_page(workspace_id: uuid.UUID, body: PageCreateIn, user: CurrentUser, s: DB):
    page = await pipeline.create_page(
        s,
        user,
        workspace_id,
        title=body.title,
        parent_id=body.parent_id,
        content_md=body.content_md,
        is_folder=body.is_folder,
        status=body.status,
        visibility=body.visibility,
        tags=body.tags,
        metadata=body.metadata,
    )
    return await serializers.page_detail_out(s, page)


@router.get("/pages/{page_id}/children", response_model=list[ChildPageOut])
async def list_children(page_id: uuid.UUID, user: CurrentUser, s: DB):
    children = await pages_service.list_children(s, user, page_id)
    return [
        ChildPageOut(
            page=await serializers.page_out(s, child),
            preview=pages_service.content_preview(child),
        )
        for child in children
    ]


@router.get("/pages/{page_id}", response_model=PageDetailOut)
async def get_page(page_id: uuid.UUID, user: CurrentUser, s: DB):
    page = await pages_service.get_for_read(s, user, page_id)
    return await serializers.page_detail_out(s, page)


@router.patch("/pages/{page_id}", response_model=PageDetailOut)
async def update_page(page_id: uuid.UUID, body: PageUpdateIn, user: CurrentUser, s: DB):
    fields = body.model_dump(exclude_unset=True)
    page = await pipeline.update_page(s, user, page_id, fields)
    return await serializers.page_detail_out(s, page)


@router.patch("/pages/{page_id}/move", response_model=PageDetailOut)
async def move_page(page_id: uuid.UUID, body: PageMoveIn, user: CurrentUser, s: DB):
    page = await pipeline.move_page(s, user, page_id, body.parent_id, body.before_id)
    return await serializers.page_detail_out(s, page)


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(page_id: uuid.UUID, user: CurrentUser, s: DB):
    await pipeline.delete_page(s, user, page_id)


@router.get("/pages/{page_id}/export")
async def export_page(page_id: uuid.UUID, user: CurrentUser, s: DB) -> Response:
    """Folder pages download as a zip of their subtree; regular pages as one .md file."""
    page = await pages_service.get_for_read(s, user, page_id)
    if page.node_type == NodeType.FILE:
        node, asset, path, _preview_kind = await vault.get_file(s, user, page.id)
        return FileResponse(
            path,
            media_type=asset.content_type,
            filename=node.title,
            content_disposition_type="attachment",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
        )
    if page.is_folder:
        filename, data = await export_service.export_folder(s, user, page_id)
        media_type = "application/zip"
        body: bytes | str = data
    else:
        filename, body = await export_service.export_page(s, user, page_id)
        media_type = "text/markdown; charset=utf-8"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": export_service.content_disposition(filename)},
    )


@router.get("/pages/{page_id}/export.pdf")
async def export_page_pdf(page_id: uuid.UUID, user: CurrentUser, s: DB) -> Response:
    """Download a regular page as a self-contained PDF with embedded images."""
    page = await pages_service.get_for_read(s, user, page_id)
    if page.node_type != NodeType.MARKDOWN or page.is_folder:
        from app.shared.exceptions import ValidationFailedError

        raise ValidationFailedError("Only regular pages can be exported as PDF")
    filename, data = await pdf_export.export_page_pdf(s, user, page_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": export_service.content_disposition(filename)},
    )


@router.get("/pages/{page_id}/versions", response_model=list[VersionOut])
async def list_versions(page_id: uuid.UUID, user: CurrentUser, s: DB):
    return await pages_service.list_versions(s, user, page_id)


@router.get("/pages/{page_id}/versions/{version_id}", response_model=VersionDetailOut)
async def get_version(page_id: uuid.UUID, version_id: uuid.UUID, user: CurrentUser, s: DB):
    return await pages_service.get_version(s, user, page_id, version_id)


@router.post("/pages/{page_id}/versions/{version_id}/restore", response_model=PageDetailOut)
async def restore_version(page_id: uuid.UUID, version_id: uuid.UUID, user: CurrentUser, s: DB):
    page = await pipeline.restore_version(s, user, page_id, version_id)
    return await serializers.page_detail_out(s, page)


@router.get("/pages/{page_id}/shares", response_model=list[ShareOut])
async def list_shares(page_id: uuid.UUID, user: CurrentUser, s: DB):
    shares = await pages_service.list_shares(s, user, page_id)
    return [ShareOut(user_id=share.user_id, name=share.user.name) for share in shares]


@router.post("/pages/{page_id}/shares", status_code=status.HTTP_201_CREATED)
async def add_share(page_id: uuid.UUID, body: ShareIn, user: CurrentUser, s: DB):
    await pages_service.add_share(s, user, page_id, body.user_id)
    return {"ok": True}


@router.delete("/pages/{page_id}/shares/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_share(page_id: uuid.UUID, target_user_id: uuid.UUID, user: CurrentUser, s: DB):
    await pages_service.remove_share(s, user, page_id, target_user_id)


@router.get("/workspaces/{workspace_id}/tags", response_model=list[TagOut])
async def list_tags(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    return [
        TagOut(name=name, page_count=count)
        for name, count in await pages_repo.list_workspace_tags(s, workspace_id)
    ]


@router.get("/workspaces/{workspace_id}/metadata-keys", response_model=list[MetadataKeyOut])
async def metadata_keys(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    keys = await pages_repo.workspace_metadata_keys(s, workspace_id)
    return [MetadataKeyOut(key=k, values=v) for k, v in keys.items()]
