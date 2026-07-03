import re
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Attachment, User
from app.modules.audit.services import audit
from app.modules.pages.infra import repo
from app.modules.pages.services import pages as pages_service
from app.shared.config.settings import settings
from app.shared.exceptions import NotFoundError, ValidationFailedError


def _safe_filename(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^\w.\-一-鿿]+", "_", name)[:200] or "file"


async def save(
    s: AsyncSession, user: User, page_id: uuid.UUID, filename: str, content_type: str, data: bytes
) -> Attachment:
    page = await pages_service.get_for_edit(s, user, page_id)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValidationFailedError(f"File exceeds {settings.max_upload_mb} MB limit")
    filename = _safe_filename(filename)
    rel_dir = Path(str(page.workspace_id))
    disk_dir = settings.uploads_dir / rel_dir
    disk_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4()
    disk_path = disk_dir / f"{file_id}_{filename}"
    disk_path.write_bytes(data)
    att = await repo.add_attachment(
        s,
        id=file_id,
        page_id=page_id,
        workspace_id=page.workspace_id,
        filename=filename,
        content_type=content_type or "application/octet-stream",
        size=len(data),
        disk_path=str(rel_dir / f"{file_id}_{filename}"),
        created_by=user.id,
    )
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="attachment.upload",
        target_type="page", target_id=page.id, target_title=page.title,
        detail={"filename": filename, "size": len(data)},
    )
    return att


async def open_for_read(
    s: AsyncSession, user: User, attachment_id: uuid.UUID
) -> tuple[Attachment, Path]:
    att = await repo.get_attachment(s, attachment_id)
    if att is None:
        raise NotFoundError("Attachment not found")
    await pages_service.get_for_read(s, user, att.page_id)  # permission = page read
    path = settings.uploads_dir / att.disk_path
    if not path.is_file():
        raise NotFoundError("Attachment file missing from disk")
    return att, path


async def list_for_page(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[Attachment]:
    await pages_service.get_for_read(s, user, page_id)
    return await repo.list_attachments(s, page_id)
