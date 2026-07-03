"""Markdown export: single page, folder subtree, or whole workspace.

Folder/workspace exports produce a zip that mirrors the page tree: a page
with children becomes a directory (its own markdown, when present, sits
inside the directory under the same name); leaf pages become plain .md files.
Only pages visible to the requesting user are included.
"""

import io
import re
import uuid
import zipfile
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, User
from app.modules.pages.infra import repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.services import policy, workspaces
from app.shared.constants import Permission

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


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


def _write_tree(
    zf: zipfile.ZipFile,
    node: Page,
    by_parent: dict[uuid.UUID | None, list[Page]],
    prefix: str,
    names: _NameRegistry,
) -> None:
    title = safe_filename(node.title)
    children = by_parent.get(node.id, [])
    if children:
        dirname = names.claim(title)
        zf.writestr(f"{prefix}{dirname}/", "")
        inner = _NameRegistry()
        if (node.content_md or "").strip() or not node.is_folder:
            zf.writestr(f"{prefix}{dirname}/{inner.claim(title)}.md", node.content_md or "")
        for child in children:
            _write_tree(zf, child, by_parent, f"{prefix}{dirname}/", inner)
    else:
        zf.writestr(f"{prefix}{names.claim(title)}.md", node.content_md or "")


def _zip_pages(roots: list[Page], by_parent: dict[uuid.UUID | None, list[Page]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        names = _NameRegistry()
        for root in roots:
            _write_tree(zf, root, by_parent, "", names)
    return buf.getvalue()


async def export_page(s: AsyncSession, user: User, page_id: uuid.UUID) -> tuple[str, str]:
    """Single page as markdown; returns (filename, content)."""
    page = await pages_service.get_for_read(s, user, page_id)
    return f"{safe_filename(page.title)}.md", page.content_md or ""


async def export_folder(s: AsyncSession, user: User, page_id: uuid.UUID) -> tuple[str, bytes]:
    """Folder subtree as a zip of markdown files; returns (filename, bytes)."""
    folder = await pages_service.get_for_read(s, user, page_id)
    pages = await repo.list_workspace(s, folder.workspace_id, policy.visible_pages_filter(user.id))
    by_parent = _children_map(pages)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        names = _NameRegistry()
        if (folder.content_md or "").strip():
            zf.writestr(f"{names.claim(safe_filename(folder.title))}.md", folder.content_md)
        for child in by_parent.get(folder.id, []):
            _write_tree(zf, child, by_parent, "", names)
    return f"{safe_filename(folder.title)}.zip", buf.getvalue()


async def export_workspace(
    s: AsyncSession, user: User, workspace_id: uuid.UUID
) -> tuple[str, bytes]:
    """All visible workspace pages as a zip preserving the folder structure."""
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    workspace, _role = await workspaces.get_for_user(s, user, workspace_id)
    pages = await repo.list_workspace(s, workspace_id, policy.visible_pages_filter(user.id))
    by_parent = _children_map(pages)
    data = _zip_pages(by_parent.get(None, []), by_parent)
    return f"{safe_filename(workspace.name, fallback='workspace')}.zip", data
