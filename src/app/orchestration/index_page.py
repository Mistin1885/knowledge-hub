"""Cross-module pipeline for page content changes.

Interface layers (API routers, collab snapshots, MCP) call these instead of
stitching modules together themselves."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, User
from app.modules.links.domain import parser
from app.modules.links.infra import repo as links_repo
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import pages as pages_service
from app.modules.search.domain import sanitize
from app.modules.search.services import indexer
from app.shared.constants import PageStatus, PageVisibility


async def index_page(s: AsyncSession, page: Page, *, title_changed: bool = False) -> None:
    """Refresh everything derived from content: links, search text, frontmatter
    tags/metadata, chunks + embeddings. Idempotent."""
    doc = parser.parse_document(page.content_md)

    plain = sanitize.sanitize_for_search(doc.plain_text)
    page.search_text = f"{page.title}\n{plain}"[: sanitize.MAX_SEARCH_TEXT_CHARS]

    await links_repo.replace_links(s, page, doc.links)
    await links_repo.resolve_pending_links_to(s, page)
    if title_changed:
        # links typed as [[New Title]] elsewhere may now resolve to this page
        await links_repo.resolve_pending_links_to(s, page)

    if doc.frontmatter_tags:
        existing = set(await pages_repo.get_page_tags(s, page.id))
        await pages_repo.set_page_tags(s, page, sorted(existing | set(doc.frontmatter_tags)))
    if doc.frontmatter:
        await pages_repo.merge_page_metadata(
            s, page.id, {k: str(v) for k, v in doc.frontmatter.items()}
        )

    await indexer.index_page_chunks(s, page)


async def create_page(
    s: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    *,
    title: str,
    parent_id: uuid.UUID | None = None,
    content_md: str = "",
    is_folder: bool = False,
    status: PageStatus = PageStatus.PUBLISHED,
    visibility: PageVisibility = PageVisibility.WORKSPACE,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> Page:
    page = await pages_service.create(
        s, user, workspace_id,
        title=title, parent_id=parent_id, content_md=content_md,
        is_folder=is_folder, status=status, visibility=visibility,
    )
    if tags:
        await pages_repo.set_page_tags(s, page, tags)
    if metadata:
        await pages_repo.set_page_metadata(s, page.id, {k: str(v) for k, v in metadata.items()})
    await index_page(s, page, title_changed=True)
    return page


async def update_page(s: AsyncSession, user: User, page_id: uuid.UUID, fields: dict) -> Page:
    from app.modules.audit.services import audit
    from app.modules.collab.services import rooms
    from app.shared.exceptions import ConflictError

    page = await pages_service.get_for_edit(s, user, page_id)
    if "content_md" in fields and fields["content_md"] is not None:
        if rooms.manager.has_active_room(page_id):
            raise ConflictError(
                "Page is being edited in a live collaboration session; content updates must go through it"
            )
    content_changed, title_changed = await pages_service.apply_update(s, user, page, fields)
    if content_changed or title_changed:
        await index_page(s, page, title_changed=title_changed)
        await pages_repo.add_version(s, page, user.id)
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="page.update",
        target_type="page", target_id=page.id, target_title=page.title,
        detail={"fields": sorted(k for k, v in fields.items() if v is not None)},
    )
    return page


async def delete_page(s: AsyncSession, user: User, page_id: uuid.UUID) -> None:
    page = await pages_service.get_for_edit(s, user, page_id)
    # keep inbound links as unresolved instead of cascade-deleting backlink rows
    await links_repo.unresolve_links_to(s, page.id)
    await pages_service.delete(s, user, page)


async def restore_version(
    s: AsyncSession, user: User, page_id: uuid.UUID, version_id: uuid.UUID
) -> Page:
    from app.modules.audit.services import audit

    page = await pages_service.get_for_edit(s, user, page_id)
    version = await pages_service.get_version(s, user, page_id, version_id)
    page.title = version.title
    page.content_md = version.content_md
    page.updated_by = user.id
    await index_page(s, page, title_changed=True)
    await pages_repo.add_version(s, page, user.id, summary=f"Restored v{version.version}")
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="page.restore",
        target_type="page", target_id=page.id, target_title=page.title,
        detail={"restored_version": version.version},
    )
    return page


async def snapshot_from_collab(
    s: AsyncSession,
    page_id: uuid.UUID,
    content_md: str,
    editor_ids: list[uuid.UUID],
    *,
    create_version: bool = False,
) -> None:
    """Persist a collab-session snapshot: content + reindex. Debounced saves pass
    create_version=False; the session-end save passes True so one version row
    captures the whole editing session."""
    from app.infra.db.models import User as UserModel

    page = await pages_repo.get(s, page_id)
    if page is None:
        return
    if page.content_md != content_md:
        page.content_md = content_md
        if editor_ids:
            page.updated_by = editor_ids[-1]
        await index_page(s, page)
    if create_version:
        last = await pages_repo.latest_version(s, page_id)
        if last is None or last.content_md != page.content_md:
            author = editor_ids[-1] if editor_ids else None
            if author is not None and await s.get(UserModel, author) is None:
                author = None
            await pages_repo.add_version(s, page, author, summary="Collaborative edit")
