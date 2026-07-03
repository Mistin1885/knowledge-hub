import uuid

from fastapi import APIRouter, status

from app.api import serializers
from app.api.deps import DB, CurrentUser
from app.api.schemas.pages import (
    ChildPageOut,
    MetadataKeyOut,
    PageCreateIn,
    PageDetailOut,
    PageOut,
    PageUpdateIn,
    ShareIn,
    ShareOut,
    TagOut,
    VersionDetailOut,
    VersionOut,
)
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.services import policy
from app.orchestration import index_page as pipeline
from app.shared.constants import Permission

router = APIRouter(tags=["pages"])


@router.get("/workspaces/{workspace_id}/pages", response_model=list[PageOut])
async def list_pages(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    pages = await pages_service.list_workspace(s, user, workspace_id)
    return [await serializers.page_out(s, p) for p in pages]


@router.post(
    "/workspaces/{workspace_id}/pages",
    response_model=PageDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_page(workspace_id: uuid.UUID, body: PageCreateIn, user: CurrentUser, s: DB):
    page = await pipeline.create_page(
        s, user, workspace_id,
        title=body.title, parent_id=body.parent_id, content_md=body.content_md,
        is_folder=body.is_folder, status=body.status, visibility=body.visibility,
        tags=body.tags, metadata=body.metadata,
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


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(page_id: uuid.UUID, user: CurrentUser, s: DB):
    await pipeline.delete_page(s, user, page_id)


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
