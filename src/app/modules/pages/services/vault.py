import hashlib
import os
import re
import uuid
from pathlib import Path

import anyio
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import FileAsset, NodeAlias, Page, User
from app.modules.audit.services import audit
from app.modules.pages.infra import repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.services import policy
from app.shared.config.settings import settings
from app.shared.constants import NodeType, PageStatus, PageVisibility, Permission
from app.shared.exceptions import ConflictError, NotFoundError, ValidationFailedError

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_CHUNK_SIZE = 1024 * 1024


def safe_filename(name: str) -> str:
    cleaned = _FORBIDDEN.sub("_", Path(name).name).strip().rstrip(".")
    return cleaned[:255] or "file"


def detected_media(header: bytes, supplied: str) -> tuple[str, str | None]:
    """Return a safe media type and browser preview kind from magic bytes."""
    if header.startswith(b"%PDF-"):
        return "application/pdf", "pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "image"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "image"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", "image"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp", "image"
    if len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] in {b"avif", b"avis"}:
        return "image/avif", "image"
    media = supplied.strip().lower()[:120]
    if not media or any(ch in media for ch in "\r\n"):
        media = "application/octet-stream"
    # Never persist a browser-previewable type when its signature did not
    # validate; otherwise a spoofed multipart header would make the UI offer
    # an inline preview even though the preview endpoint correctly rejects it.
    if preview_kind_for_content_type(media):
        media = "application/octet-stream"
    return media, None


def preview_kind_for_content_type(content_type: str) -> str | None:
    if content_type == "application/pdf":
        return "pdf"
    if content_type in {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}:
        return "image"
    return None


async def _unique_sibling_name(
    s: AsyncSession, workspace_id: uuid.UUID, parent_id: uuid.UUID | None, filename: str
) -> str:
    stem, suffix = Path(filename).stem, Path(filename).suffix
    candidate = filename
    n = 2
    while True:
        q = select(Page.id).where(
            Page.workspace_id == workspace_id, func.lower(Page.title) == candidate.lower()
        )
        q = q.where(Page.parent_id == parent_id) if parent_id else q.where(Page.parent_id.is_(None))
        if await s.scalar(q) is None:
            return candidate
        candidate = f"{stem} ({n}){suffix}"
        n += 1


async def upload_file(
    s: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    file: UploadFile,
    parent_id: uuid.UUID | None = None,
) -> tuple[Page, FileAsset, str | None]:
    if parent_id is None:
        await policy.require_permission(s, user, workspace_id, Permission.WRITE)
        visibility = PageVisibility.WORKSPACE
        owner_id = user.id
    else:
        parent = await pages_service.get_for_edit(s, user, parent_id)
        if parent.workspace_id != workspace_id:
            raise ValidationFailedError("Parent node is not in this workspace")
        if parent.node_type == NodeType.FILE:
            raise ValidationFailedError("Files cannot contain child nodes")
        visibility = parent.visibility
        owner_id = parent.owner_id or user.id

    filename = await _unique_sibling_name(
        s, workspace_id, parent_id, safe_filename(file.filename or "file")
    )
    file_id = uuid.uuid4()
    rel_dir = Path(str(workspace_id))
    disk_dir = settings.uploads_dir / rel_dir
    disk_dir.mkdir(parents=True, exist_ok=True)
    temp_path = disk_dir / f".{file_id}.upload"
    final_path = disk_dir / f"{file_id}_{filename}"
    size = 0
    digest = hashlib.sha256()
    header = b""
    max_bytes = settings.max_upload_bytes

    try:
        async with await anyio.open_file(temp_path, "wb") as output:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    configured_limit = settings.max_upload or f"{settings.max_upload_mb}M"
                    raise ValidationFailedError(f"File exceeds {configured_limit} limit")
                if len(header) < 32:
                    header = (header + chunk)[:32]
                digest.update(chunk)
                await output.write(chunk)
        media_type, preview_kind = detected_media(header, file.content_type or "")
        position = await repo.max_sibling_position(s, workspace_id, parent_id) + 1.0
        node = Page(
            id=file_id,
            workspace_id=workspace_id,
            parent_id=parent_id,
            title=filename,
            content_md="",
            status=PageStatus.PUBLISHED,
            visibility=visibility,
            is_folder=False,
            node_type=NodeType.FILE,
            position=position,
            version=0,
            owner_id=owner_id,
            created_by=user.id,
            updated_by=user.id,
            search_text=filename,
        )
        asset = FileAsset(
            node_id=file_id,
            content_type=media_type,
            size=size,
            disk_path=str(rel_dir / final_path.name),
            checksum_sha256=digest.hexdigest(),
        )
        s.add_all([node, asset])
        await s.flush()
        if parent_id is not None and visibility == PageVisibility.PRIVATE:
            for share in await repo.list_shares(s, parent_id):
                await repo.add_share(s, node.id, share.user_id)
        os.replace(temp_path, final_path)
        await audit.record(
            s,
            workspace_id=workspace_id,
            actor_id=user.id,
            action="file.upload",
            target_type="file",
            target_id=node.id,
            target_title=node.title,
            detail={"size": size, "content_type": media_type},
        )
        from app.modules.links.infra import repo as links_repo

        await links_repo.resolve_pending_links_to(s, node)
        return node, asset, preview_kind
    except BaseException:
        temp_path.unlink(missing_ok=True)
        if final_path.is_file():
            final_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


async def get_file(
    s: AsyncSession, user: User, node_id: uuid.UUID
) -> tuple[Page, FileAsset, Path, str | None]:
    node = await pages_service.get_for_read(s, user, node_id)
    if node.node_type != NodeType.FILE:
        raise NotFoundError("File not found")
    asset = await repo.get_file_asset(s, node.id)
    if asset is None:
        raise NotFoundError("File payload not found")
    path = settings.uploads_dir / asset.disk_path
    if not path.is_file():
        raise NotFoundError("File payload is missing from disk")
    with path.open("rb") as source:
        header = source.read(32)
    media_type, preview_kind = detected_media(header, asset.content_type)
    return node, asset, path, preview_kind


async def get_legacy_file(
    s: AsyncSession, user: User, attachment_id: uuid.UUID
) -> tuple[Page, FileAsset, Path, str | None] | None:
    asset = await repo.get_file_asset_by_legacy_id(s, attachment_id)
    if asset is None:
        asset = await repo.get_file_asset(s, attachment_id)
    if asset is None:
        return None
    return await get_file(s, user, asset.node_id)


async def canonical_path(s: AsyncSession, node: Page) -> str:
    parts = [node.title]
    parent_id = node.parent_id
    for _ in range(100):
        if parent_id is None:
            break
        parent = await repo.get(s, parent_id)
        if parent is None:
            break
        parts.append(parent.title)
        parent_id = parent.parent_id
    return "/".join(reversed(parts))


async def record_alias(s: AsyncSession, node: Page, path: str) -> None:
    existing = await s.scalar(
        select(NodeAlias).where(
            NodeAlias.workspace_id == node.workspace_id, func.lower(NodeAlias.path) == path.lower()
        )
    )
    if existing is None:
        s.add(NodeAlias(workspace_id=node.workspace_id, node_id=node.id, path=path))


async def subtree_paths(s: AsyncSession, node: Page) -> list[tuple[Page, str]]:
    nodes = await repo.list_workspace(s, node.workspace_id, Page.id.is_not(None))
    by_parent: dict[uuid.UUID | None, list[Page]] = {}
    for item in nodes:
        by_parent.setdefault(item.parent_id, []).append(item)
    result: list[tuple[Page, str]] = []
    stack = [node]
    while stack:
        current = stack.pop()
        result.append((current, await canonical_path(s, current)))
        stack.extend(by_parent.get(current.id, []))
    return result


async def resolve_target(
    s: AsyncSession, workspace_id: uuid.UUID, target: str
) -> Page | None:
    raw = target.split("#", 1)[0].strip().strip("/")
    if not raw:
        return None
    nodes = await repo.list_workspace(s, workspace_id, Page.id.is_not(None))
    exact: list[Page] = []
    basename: list[Page] = []
    for node in nodes:
        if (await canonical_path(s, node)).lower() == raw.lower():
            exact.append(node)
        if node.title.lower() == raw.lower() or (
            node.node_type == NodeType.MARKDOWN
            and node.title.lower() == re.sub(r"\.md$", "", raw, flags=re.IGNORECASE).lower()
        ):
            basename.append(node)
    if len(exact) == 1:
        return exact[0]
    if len(basename) == 1:
        return basename[0]
    alias = await s.scalar(
        select(NodeAlias).where(
            NodeAlias.workspace_id == workspace_id, func.lower(NodeAlias.path) == raw.lower()
        )
    )
    return await repo.get(s, alias.node_id) if alias else None


async def ensure_move_allowed(s: AsyncSession, node: Page, parent_id: uuid.UUID | None) -> None:
    duplicate = select(Page.id).where(
        Page.workspace_id == node.workspace_id,
        Page.id != node.id,
        func.lower(Page.title) == node.title.lower(),
    )
    duplicate = (
        duplicate.where(Page.parent_id == parent_id)
        if parent_id
        else duplicate.where(Page.parent_id.is_(None))
    )
    if await s.scalar(duplicate):
        raise ConflictError(f'A node named "{node.title}" already exists there')
    if parent_id is None:
        return
    parent = await repo.get(s, parent_id)
    if parent is None or parent.workspace_id != node.workspace_id:
        raise ValidationFailedError("Parent node not found in this workspace")
    if parent.node_type == NodeType.FILE:
        raise ValidationFailedError("Files cannot contain child nodes")
    if parent.id == node.id or await repo.is_descendant(s, node.id, parent.id):
        raise ValidationFailedError("Cannot move a node into its own subtree")


async def ensure_rename_available(s: AsyncSession, node: Page, title: str) -> None:
    q = select(Page.id).where(
        Page.workspace_id == node.workspace_id,
        Page.id != node.id,
        func.lower(Page.title) == title.lower(),
    )
    q = q.where(Page.parent_id == node.parent_id) if node.parent_id else q.where(Page.parent_id.is_(None))
    if await s.scalar(q):
        raise ConflictError(f'A node named "{title}" already exists here')


async def delete_payloads_for_subtree(
    s: AsyncSession, node: Page
) -> tuple[list[Path], list[uuid.UUID]]:
    nodes = await repo.list_workspace(s, node.workspace_id, Page.id.is_not(None))
    by_parent: dict[uuid.UUID | None, list[Page]] = {}
    for item in nodes:
        by_parent.setdefault(item.parent_id, []).append(item)
    ids: list[uuid.UUID] = []
    stack = [node]
    while stack:
        current = stack.pop()
        ids.append(current.id)
        stack.extend(by_parent.get(current.id, []))
    assets = await repo.file_assets_for_nodes(s, ids)
    paths = [settings.uploads_dir / asset.disk_path for asset in assets]
    legacy_ids = [asset.legacy_attachment_id for asset in assets if asset.legacy_attachment_id]
    return paths, legacy_ids
