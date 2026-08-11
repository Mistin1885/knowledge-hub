"""Markdown export: single page, folder subtree, or whole workspace.

Folder/workspace exports produce a zip that mirrors the page tree: a page
with children becomes a directory (its own markdown, when present, sits
inside the directory under the same name); leaf pages become plain .md files.
Only pages visible to the requesting user are included.
"""

import io
import posixpath
import re
import uuid
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, User
from app.modules.pages.infra import repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.services import policy, workspaces
from app.shared.config.settings import settings
from app.shared.constants import NodeType, Permission

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_INTERNAL_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\(/api/v1/(?:files/([0-9a-f-]{36})/preview|"
    r"attachments/([0-9a-f-]{36})(?:/[^)\n]+)?)\)",
    flags=re.IGNORECASE,
)


def safe_filename(title: str, fallback: str = "Untitled") -> str:
    name = _FORBIDDEN.sub("", title).strip().rstrip(".")
    return name or fallback


def content_disposition(filename: str) -> str:
    """RFC 5987 attachment header that survives non-ASCII titles."""
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "'")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


class _NameRegistry:
    """Deduplicate entry names within a single zip directory."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def claim(self, name: str) -> str:
        candidate = name
        n = 2
        while candidate.lower() in self._used:
            candidate = f"{name} ({n})"
            n += 1
        self._used.add(candidate.lower())
        return candidate


def _children_map(pages: list[Page]) -> dict[uuid.UUID | None, list[Page]]:
    ids = {p.id for p in pages}
    by_parent: dict[uuid.UUID | None, list[Page]] = {}
    for page in pages:
        key = page.parent_id if page.parent_id in ids else None
        by_parent.setdefault(key, []).append(page)
    for siblings in by_parent.values():
        siblings.sort(key=lambda p: (p.position, p.title))
    return by_parent


def rewrite_internal_images_for_export(
    content: str,
    source_path: str,
    file_paths: dict[uuid.UUID, str],
    *,
    single_markdown: bool = False,
) -> str:
    """Convert authenticated app URLs to portable Obsidian image links.

    Unknown IDs remain byte-for-byte unchanged.  A standalone Markdown export
    uses an Obsidian basename embed because it cannot carry binary payloads;
    ZIP exports use exact relative Markdown paths to the included files.
    """

    def replace(match: re.Match[str]) -> str:
        node_id = uuid.UUID(match.group(2) or match.group(3))
        target = file_paths.get(node_id)
        if target is None:
            return match.group(0)
        if single_markdown:
            return f"![[{PurePosixPath(target).name}]]"
        source_dir = posixpath.dirname(source_path) or "."
        relative = posixpath.relpath(target, source_dir)
        alt = match.group(1)
        return f"![{alt}](<{relative}>)"

    return _INTERNAL_IMAGE_RE.sub(replace, content)


def _plan_nodes(
    nodes: list[Page],
    by_parent: dict[uuid.UUID | None, list[Page]],
    prefix: str,
    names: _NameRegistry,
    page_paths: dict[uuid.UUID, str],
    file_paths: dict[uuid.UUID, str],
    directories: set[str],
) -> None:
    for node in nodes:
        title = safe_filename(node.title)
        if node.node_type == NodeType.FILE:
            file_paths[node.id] = f"{prefix}{names.claim(title)}"
            continue
        children = by_parent.get(node.id, [])
        if children:
            dirname = names.claim(title)
            directory = f"{prefix}{dirname}/"
            directories.add(directory)
            inner = _NameRegistry()
            if (node.content_md or "").strip() or not node.is_folder:
                page_paths[node.id] = f"{directory}{inner.claim(title)}.md"
            _plan_nodes(
                children,
                by_parent,
                directory,
                inner,
                page_paths,
                file_paths,
                directories,
            )
        else:
            page_paths[node.id] = f"{prefix}{names.claim(title)}.md"


def _zip_pages(
    roots: list[Page],
    by_parent: dict[uuid.UUID | None, list[Page]],
    assets: dict[uuid.UUID, str],
    *,
    root_note: Page | None = None,
) -> bytes:
    nodes = {page.id: page for siblings in by_parent.values() for page in siblings}
    page_paths: dict[uuid.UUID, str] = {}
    file_paths: dict[uuid.UUID, str] = {}
    directories: set[str] = set()
    names = _NameRegistry()
    if root_note is not None and (root_note.content_md or "").strip():
        page_paths[root_note.id] = f"{names.claim(safe_filename(root_note.title))}.md"
        nodes[root_note.id] = root_note
    _plan_nodes(roots, by_parent, "", names, page_paths, file_paths, directories)
    included_file_paths = {
        node_id: arcname
        for node_id, arcname in file_paths.items()
        if (disk_path := assets.get(node_id))
        and (settings.uploads_dir / disk_path).is_file()
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for directory in sorted(directories):
            zf.writestr(directory, "")
        for node_id, arcname in sorted(page_paths.items(), key=lambda item: item[1]):
            page = nodes[node_id]
            content = rewrite_internal_images_for_export(
                page.content_md or "", arcname, included_file_paths
            )
            zf.writestr(arcname, content)
        for node_id, arcname in sorted(
            included_file_paths.items(), key=lambda item: item[1]
        ):
            zf.write(settings.uploads_dir / assets[node_id], arcname)
    return buf.getvalue()


async def export_page(s: AsyncSession, user: User, page_id: uuid.UUID) -> tuple[str, str]:
    """Single page as markdown; returns (filename, content)."""
    page = await pages_service.get_for_read(s, user, page_id)
    file_nodes = await repo.list_workspace(
        s, page.workspace_id, policy.visible_pages_filter(user.id)
    )
    file_paths = {
        node.id: node.title for node in file_nodes if node.node_type == NodeType.FILE
    }
    filename = f"{safe_filename(page.title)}.md"
    return filename, rewrite_internal_images_for_export(
        page.content_md or "", filename, file_paths, single_markdown=True
    )


async def export_folder(s: AsyncSession, user: User, page_id: uuid.UUID) -> tuple[str, bytes]:
    """Folder subtree as a zip of markdown files; returns (filename, bytes)."""
    folder = await pages_service.get_for_read(s, user, page_id)
    pages = await repo.list_workspace(s, folder.workspace_id, policy.visible_pages_filter(user.id))
    by_parent = _children_map(pages)
    assets = {
        asset.node_id: asset.disk_path
        for asset in await repo.file_assets_for_nodes(s, [page.id for page in pages])
    }

    data = _zip_pages(
        by_parent.get(folder.id, []), by_parent, assets, root_note=folder
    )
    return f"{safe_filename(folder.title)}.zip", data


async def export_workspace(
    s: AsyncSession, user: User, workspace_id: uuid.UUID
) -> tuple[str, bytes]:
    """All visible workspace pages as a zip preserving the folder structure."""
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    workspace, _role = await workspaces.get_for_user(s, user, workspace_id)
    pages = await repo.list_workspace(s, workspace_id, policy.visible_pages_filter(user.id))
    by_parent = _children_map(pages)
    assets = {
        asset.node_id: asset.disk_path
        for asset in await repo.file_assets_for_nodes(s, [page.id for page in pages])
    }
    data = _zip_pages(by_parent.get(None, []), by_parent, assets)
    return f"{safe_filename(workspace.name, fallback='workspace')}.zip", data
