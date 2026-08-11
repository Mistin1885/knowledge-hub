import uuid

from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api import serializers
from app.api.deps import DB, CurrentUser
from app.api.schemas.pages import PageOut, VaultImportOut
from app.modules.pages.services import vault
from app.shared.exceptions import ValidationFailedError

router = APIRouter(tags=["files"])


@router.post(
    "/workspaces/{workspace_id}/files",
    response_model=PageOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    workspace_id: uuid.UUID,
    file: UploadFile,
    user: CurrentUser,
    s: DB,
    parent_id: uuid.UUID | None = Query(None),
):
    node, _asset, _preview_kind = await vault.upload_file(
        s, user, workspace_id, file, parent_id=parent_id
    )
    return await serializers.page_out(s, node)


@router.post(
    "/workspaces/{workspace_id}/import",
    response_model=VaultImportOut,
    status_code=status.HTTP_200_OK,
)
async def import_vault_item(
    workspace_id: uuid.UUID,
    file: UploadFile,
    user: CurrentUser,
    s: DB,
    relative_path: str = Query(..., min_length=1, max_length=4000),
    parent_id: uuid.UUID | None = Query(None),
):
    action, node, folders_created, warnings = await vault.import_vault_item(
        s,
        user,
        workspace_id,
        file,
        relative_path=relative_path,
        base_parent_id=parent_id,
    )
    return VaultImportOut(
        action=action,
        page=await serializers.page_out(s, node),
        folders_created=folders_created,
        warnings=warnings,
    )


@router.get("/files/{node_id}/preview")
async def preview_file(node_id: uuid.UUID, user: CurrentUser, s: DB):
    node, asset, path, preview_kind = await vault.get_file(s, user, node_id)
    if preview_kind is None:
        raise ValidationFailedError("This file type is not available for browser preview")
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=node.title,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.get("/files/{node_id}/download")
async def download_file(node_id: uuid.UUID, user: CurrentUser, s: DB):
    node, asset, path, _preview_kind = await vault.get_file(s, user, node_id)
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=node.title,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
