import uuid

from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DB, CurrentUser
from app.api.schemas.pages import AttachmentOut
from app.modules.pages.services import attachments as attachments_service

router = APIRouter(tags=["attachments"])


def _out(att) -> AttachmentOut:
    return AttachmentOut(
        id=att.id,
        filename=att.filename,
        content_type=att.content_type,
        size=att.size,
        url=f"/api/v1/attachments/{att.id}/{att.filename}",
    )


@router.post(
    "/pages/{page_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload(page_id: uuid.UUID, file: UploadFile, user: CurrentUser, s: DB):
    data = await file.read()
    att = await attachments_service.save(
        s, user, page_id, file.filename or "file", file.content_type or "", data
    )
    return _out(att)


@router.get("/pages/{page_id}/attachments", response_model=list[AttachmentOut])
async def list_attachments(page_id: uuid.UUID, user: CurrentUser, s: DB):
    return [_out(a) for a in await attachments_service.list_for_page(s, user, page_id)]


@router.get("/attachments/{attachment_id}/{filename}")
async def download(attachment_id: uuid.UUID, filename: str, user: CurrentUser, s: DB):
    att, path = await attachments_service.open_for_read(s, user, attachment_id)
    return FileResponse(path, media_type=att.content_type, filename=att.filename)
