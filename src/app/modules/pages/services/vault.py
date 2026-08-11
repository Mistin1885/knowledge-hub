import hashlib
import os
import posixpath
import re
import uuid
from pathlib import Path
from urllib.parse import unquote

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
_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"}
_OBSIDIAN_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")


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


def _relative_parts(relative_path: str) -> list[str]:
    raw_parts = relative_path.replace("\\", "/").split("/")
    if not raw_parts or any(part == ".." for part in raw_parts):
        raise ValidationFailedError("Import path must stay inside the selected folder")
    parts = [part.strip() for part in raw_parts if part.strip() not in {"", "."}]
    if not parts:
        raise ValidationFailedError("Import path is required")
    cleaned = [_FORBIDDEN.sub("_", part).strip().rstrip(".") for part in parts]
    if any(not part for part in cleaned):
        raise ValidationFailedError("Import path contains an invalid name")
    return cleaned


async def _ensure_import_folders(
    s: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    base_parent_id: uuid.UUID | None,
    parts: list[str],
) -> tuple[uuid.UUID | None, int]:
    """Resolve/create a relative directory chain without inventing (2) copies."""
    from app.orchestration import index_page as pipeline

    parent_id = base_parent_id
    created = 0
    for raw_name in parts:
        name = raw_name[:500]
        existing = await repo.find_sibling(s, workspace_id, parent_id, name)
        if existing is not None:
            if existing.node_type == NodeType.FILE:
                raise ConflictError(f'Cannot create folder "{name}" because a file exists there')
            if existing.node_type != NodeType.FOLDER or not existing.is_folder:
                existing = await pipeline.update_page(s, user, existing.id, {"is_folder": True})
            parent_id = existing.id
            continue
        folder = await pipeline.create_page(
            s,
            user,
            workspace_id,
            title=name,
            parent_id=parent_id,
            is_folder=True,
        )
        parent_id = folder.id
        created += 1
    return parent_id, created


def _paths_for_nodes(nodes: list[Page]) -> dict[uuid.UUID, str]:
    by_id = {node.id: node for node in nodes}
    cache: dict[uuid.UUID, str] = {}

    def build(node: Page, visiting: set[uuid.UUID]) -> str:
        if node.id in cache:
            return cache[node.id]
        if node.id in visiting or node.parent_id is None or node.parent_id not in by_id:
            result = node.title
        else:
            result = f"{build(by_id[node.parent_id], visiting | {node.id})}/{node.title}"
        cache[node.id] = result
        return result

    for node in nodes:
        build(node, set())
    return cache


async def rewrite_obsidian_images(
    s: AsyncSession,
    workspace_id: uuid.UUID,
    source_parent_id: uuid.UUID | None,
    content: str,
) -> tuple[str, list[str]]:
    """Turn local Obsidian image references into authenticated preview URLs.

    Resolution mirrors how people organise real vaults: current directory,
    then each ancestor, then an exact vault path, then a unique basename.
    Ambiguous basenames remain untouched and produce a visible import warning.
    """
    nodes = await repo.list_workspace(s, workspace_id, Page.id.is_not(None))
    paths = _paths_for_nodes(nodes)
    assets = await repo.file_assets_for_nodes(s, [node.id for node in nodes])
    asset_by_id = {asset.node_id: asset for asset in assets}
    file_nodes = [node for node in nodes if node.id in asset_by_id]
    by_path = {paths[node.id].lower(): node for node in file_nodes}
    by_basename: dict[str, list[Page]] = {}
    for node in file_nodes:
        by_basename.setdefault(node.title.lower(), []).append(node)
    source_dir = paths.get(source_parent_id, "") if source_parent_id else ""
    warnings: list[str] = []

    def resolve(raw_target: str) -> Page | None:
        target = unquote(raw_target.strip().strip("<>")).replace("\\", "/")
        target = target.split("#", 1)[0].split("?", 1)[0].strip()
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, flags=re.IGNORECASE):
            return None
        target = target.lstrip("/")
        candidates: list[str] = []
        ancestor = source_dir
        while True:
            candidate = posixpath.normpath(posixpath.join(ancestor, target)).lstrip("./")
            candidates.append(candidate)
            if not ancestor or "/" not in ancestor:
                if ancestor:
                    ancestor = ""
                    continue
                break
            ancestor = ancestor.rsplit("/", 1)[0]
        candidates.append(posixpath.normpath(target).lstrip("./"))
        for candidate in candidates:
            if node := by_path.get(candidate.lower()):
                return node
        suffix = "/" + posixpath.normpath(target).lower().lstrip("./")
        suffix_matches = [node for node in file_nodes if paths[node.id].lower().endswith(suffix)]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        basename_matches = by_basename.get(posixpath.basename(target).lower(), [])
        return basename_matches[0] if len(basename_matches) == 1 else None

    def image_node(raw_target: str) -> Page | None:
        node = resolve(raw_target)
        if node is None:
            return None
        asset = asset_by_id[node.id]
        return node if preview_kind_for_content_type(asset.content_type) == "image" else None

    def warn(raw_target: str) -> None:
        target = raw_target.split("|", 1)[0].strip()
        if Path(target).suffix.lower() in _IMAGE_SUFFIXES:
            message = f'Image not found: {target}'
            if message not in warnings and len(warnings) < 25:
                warnings.append(message)

    def replace_embed(match: re.Match[str]) -> str:
        spec = match.group(1)
        target, _, alias = spec.partition("|")
        node = image_node(target)
        if node is None:
            warn(target)
            return match.group(0)
        alt = alias.strip() or Path(target.split("#", 1)[0]).stem
        return f"![{alt}](/api/v1/files/{node.id}/preview)"

    def replace_markdown(match: re.Match[str]) -> str:
        alt, inner = match.group(1), match.group(2).strip()
        if inner.startswith("<") and ">" in inner:
            raw = inner[1 : inner.index(">")]
        else:
            # Markdown permits an optional quoted title after the destination.
            raw = re.sub(r"\s+(['\"]).*\1$", "", inner).strip()
        if re.match(r"^(?:https?|data):", raw, flags=re.IGNORECASE) or raw.startswith("/api/"):
            return match.group(0)
        node = image_node(raw)
        if node is None:
            warn(raw)
            return match.group(0)
        return f"![{alt}](/api/v1/files/{node.id}/preview)"

    rewritten = _OBSIDIAN_EMBED_RE.sub(replace_embed, content)
    rewritten = _MARKDOWN_IMAGE_RE.sub(replace_markdown, rewritten)
    return rewritten, warnings


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
    # Payload names are internal.  Keep them UUID-only so a valid 255-byte
    # user-facing filename cannot overflow the filesystem once prefixed.
    final_path = disk_dir / str(file_id)
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
        # FileAsset intentionally has no ORM relationship back to Page, so
        # SQLAlchemy cannot infer the foreign-key insert order from add_all().
        # Flush the node first to make this reliable on PostgreSQL (SQLite test
        # setups may not enforce the foreign key and therefore hide the bug).
        s.add(node)
        await s.flush()
        s.add(asset)
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


async def import_vault_item(
    s: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    file: UploadFile,
    *,
    relative_path: str,
    base_parent_id: uuid.UUID | None = None,
) -> tuple[str, Page, int, list[str]]:
    """Idempotently import one file at a stable relative Vault path."""
    from app.orchestration import index_page as pipeline

    if base_parent_id is None:
        await policy.require_permission(s, user, workspace_id, Permission.WRITE)
    else:
        base_parent = await pages_service.get_for_edit(s, user, base_parent_id)
        if base_parent.workspace_id != workspace_id or base_parent.node_type == NodeType.FILE:
            raise ValidationFailedError("Import destination is not a folder in this workspace")

    parts = _relative_parts(relative_path)
    filename = parts[-1]
    parent_id, folders_created = await _ensure_import_folders(
        s, user, workspace_id, base_parent_id, parts[:-1]
    )
    suffix = Path(filename).suffix.lower()

    if suffix in _MARKDOWN_SUFFIXES:
        try:
            payload = await file.read(settings.max_upload_bytes + 1)
            if len(payload) > settings.max_upload_bytes:
                raise ValidationFailedError("Markdown file exceeds the configured upload limit")
            warnings: list[str] = []
            try:
                content = payload.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = payload.decode("utf-8", errors="replace")
                warnings.append(f"Invalid UTF-8 bytes replaced in {relative_path}")
            content, image_warnings = await rewrite_obsidian_images(
                s, workspace_id, parent_id, content
            )
            warnings.extend(image_warnings)
            title = Path(filename).stem.strip()[:500] or "Untitled"
            parent = await repo.get(s, parent_id) if parent_id else None
            # Preserve the existing export/import round trip: Folder/Folder.md
            # is the folder's own note rather than a duplicate child page.
            existing = (
                parent
                if parent is not None
                and parent.node_type == NodeType.FOLDER
                and parent.title.lower() == title.lower()
                else await repo.find_sibling(s, workspace_id, parent_id, title)
            )
            if existing is None:
                page = await pipeline.create_page(
                    s,
                    user,
                    workspace_id,
                    title=title,
                    parent_id=parent_id,
                    content_md=content,
                )
                return "created", page, folders_created, warnings
            if existing.node_type == NodeType.FILE:
                raise ConflictError(f'Cannot import note "{title}" because a file exists there')
            if existing.content_md == content:
                return "skipped", existing, folders_created, warnings
            page = await pipeline.update_page(s, user, existing.id, {"content_md": content})
            return "updated", page, folders_created, warnings
        finally:
            await file.close()

    safe_name = safe_filename(filename)
    existing = await repo.find_sibling(s, workspace_id, parent_id, safe_name)
    if existing is not None and existing.node_type != NodeType.FILE:
        await file.close()
        raise ConflictError(f'Cannot import file "{safe_name}" because a page exists there')

    file_id = existing.id if existing else uuid.uuid4()
    rel_dir = Path(str(workspace_id))
    disk_dir = settings.uploads_dir / rel_dir
    disk_dir.mkdir(parents=True, exist_ok=True)
    temp_path = disk_dir / f".{uuid.uuid4()}.import"
    size = 0
    digest = hashlib.sha256()
    header = b""
    try:
        async with await anyio.open_file(temp_path, "wb") as output:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    configured_limit = settings.max_upload or f"{settings.max_upload_mb}M"
                    raise ValidationFailedError(f"File exceeds {configured_limit} limit")
                if len(header) < 32:
                    header = (header + chunk)[:32]
                digest.update(chunk)
                await output.write(chunk)

        checksum = digest.hexdigest()
        if existing is not None:
            asset = await repo.get_file_asset(s, existing.id)
            if asset is not None and asset.size == size and asset.checksum_sha256 == checksum:
                temp_path.unlink(missing_ok=True)
                return "skipped", existing, folders_created, []
            media_type, _preview_kind = detected_media(header, file.content_type or "")
            final_path = (
                settings.uploads_dir / asset.disk_path
                if asset is not None
                else disk_dir / str(file_id)
            )
            os.replace(temp_path, final_path)
            if asset is None:
                asset = FileAsset(
                    node_id=existing.id,
                    content_type=media_type,
                    size=size,
                    disk_path=str(rel_dir / final_path.name),
                    checksum_sha256=checksum,
                )
                s.add(asset)
            else:
                asset.content_type = media_type
                asset.size = size
                asset.checksum_sha256 = checksum
            existing.updated_by = user.id
            existing.search_text = existing.title
            await s.flush()
            await audit.record(
                s,
                workspace_id=workspace_id,
                actor_id=user.id,
                action="file.import.update",
                target_type="file",
                target_id=existing.id,
                target_title=existing.title,
                detail={"size": size, "relative_path": relative_path},
            )
            from app.modules.links.infra import repo as links_repo

            await links_repo.resolve_pending_links_to(s, existing)
            return "updated", existing, folders_created, []

        media_type, _preview_kind = detected_media(header, file.content_type or "")
        position = await repo.max_sibling_position(s, workspace_id, parent_id) + 1.0
        parent = await repo.get(s, parent_id) if parent_id else None
        node = Page(
            id=file_id,
            workspace_id=workspace_id,
            parent_id=parent_id,
            title=safe_name,
            content_md="",
            status=PageStatus.PUBLISHED,
            visibility=parent.visibility if parent else PageVisibility.WORKSPACE,
            is_folder=False,
            node_type=NodeType.FILE,
            position=position,
            owner_id=(parent.owner_id if parent else None) or user.id,
            created_by=user.id,
            updated_by=user.id,
            search_text=safe_name,
        )
        final_path = disk_dir / str(file_id)
        asset = FileAsset(
            node_id=file_id,
            content_type=media_type,
            size=size,
            disk_path=str(rel_dir / final_path.name),
            checksum_sha256=checksum,
        )
        s.add(node)
        await s.flush()
        s.add(asset)
        await s.flush()
        os.replace(temp_path, final_path)
        await audit.record(
            s,
            workspace_id=workspace_id,
            actor_id=user.id,
            action="file.import",
            target_type="file",
            target_id=node.id,
            target_title=node.title,
            detail={"size": size, "relative_path": relative_path},
        )
        from app.modules.links.infra import repo as links_repo

        await links_repo.resolve_pending_links_to(s, node)
        return "created", node, folders_created, []
    except BaseException:
        temp_path.unlink(missing_ok=True)
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
