import uuid

from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DB, CurrentUser
from app.api.schemas.pages import AttachmentOut
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import attachments as attachments_service
from app.modules.pages.services import pages as pages_service
from app.modules.pages.services import vault
from app.modules.workspaces.services import policy

router = APIRouter(tags=["attachments"])


def _out(att) -> AttachmentOut:
    preview_kind = vault.preview_kind_for_content_type(att.content_type)
    return AttachmentOut(
        id=att.id,
        filename=att.filename,
        content_type=att.content_type,
        size=att.size,
        url=f"/api/v1/attachments/{att.id}/{att.filename}",
        created_at=att.created_at,
        preview_kind=preview_kind,
        preview_url=f"/api/v1/attachments/{att.id}/{att.filename}" if preview_kind else None,
        download_url=f"/api/v1/attachments/{att.id}/{att.filename}",
    )


def _out_file(node, asset, preview_kind: str | None) -> AttachmentOut:
    compatibility_url = f"/api/v1/attachments/{node.id}/{node.title}"
    return AttachmentOut(
        id=node.id,
        filename=node.title,
        content_type=asset.content_type,
        size=asset.size,
        url=compatibility_url,
        created_at=node.created_at,
        preview_kind=preview_kind,
        preview_url=compatibility_url if preview_kind else None,
        download_url=f"/api/v1/files/{node.id}/download",
    )


@router.post(
    "/pages/{page_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload(page_id: uuid.UUID, file: UploadFile, user: CurrentUser, s: DB):
    parent = await pages_service.get_for_edit(s, user, page_id)
    node, asset, preview_kind = await vault.upload_file(
        s, user, parent.workspace_id, file, parent_id=page_id
    )
    return _out_file(node, asset, preview_kind)


@router.get("/pages/{page_id}/attachments", response_model=list[AttachmentOut])
async def list_attachments(page_id: uuid.UUID, user: CurrentUser, s: DB):
    legacy = await attachments_service.list_for_page(s, user, page_id)
    result = [_out(a) for a in legacy]
    seen = {item.id for item in result}
    for node, asset in await pages_repo.list_file_nodes_for_parent(s, page_id):
        if node.id not in seen and await policy.can_read_page(s, user, node):
            result.append(
                _out_file(node, asset, vault.preview_kind_for_content_type(asset.content_type))
            )
    return result


@router.get("/attachments/{attachment_id}/{filename}")
async def download(attachment_id: uuid.UUID, filename: str, user: CurrentUser, s: DB):
    migrated = await vault.get_legacy_file(s, user, attachment_id)
    if migrated is not None:
        node, asset, path, preview_kind = migrated
        return FileResponse(
            path,
            media_type=asset.content_type,
            filename=node.title,
            content_disposition_type="inline" if preview_kind else "attachment",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
        )
    att, path = await attachments_service.open_for_read(s, user, attachment_id)
    return FileResponse(path, media_type=att.content_type, filename=att.filename)
