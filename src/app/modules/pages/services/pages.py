import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageShare, PageVersion, User
from app.modules.audit.services import audit
from app.modules.pages.infra import repo
from app.modules.workspaces.services import policy
from app.shared.constants import PageStatus, PageVisibility, Permission
from app.shared.exceptions import NotFoundError, ValidationFailedError


async def get_for_read(s: AsyncSession, user: User, page_id: uuid.UUID) -> Page:
    page = await repo.get(s, page_id)
    if page is None:
        raise NotFoundError("Page not found")
    await policy.require_page_read(s, user, page)
    return page


async def get_for_edit(s: AsyncSession, user: User, page_id: uuid.UUID) -> Page:
    page = await repo.get(s, page_id)
    if page is None:
        raise NotFoundError("Page not found")
    await policy.require_page_edit(s, user, page)
    return page


async def list_workspace(s: AsyncSession, user: User, workspace_id: uuid.UUID) -> list[Page]:
    await policy.require_permission(s, user, workspace_id, Permission.READ)
    return await repo.list_workspace(s, workspace_id, policy.visible_pages_filter(user.id))


async def create(
    s: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    title: str,
    parent_id: uuid.UUID | None = None,
    content_md: str = "",
    is_folder: bool = False,
    status: PageStatus = PageStatus.PUBLISHED,
    visibility: PageVisibility = PageVisibility.WORKSPACE,
) -> Page:
    await policy.require_permission(s, user, workspace_id, Permission.WRITE)
    title = title.strip()
    if not title:
        raise ValidationFailedError("Title is required")
    if parent_id is not None:
        parent = await repo.get(s, parent_id)
        if parent is None or parent.workspace_id != workspace_id:
            raise ValidationFailedError("Parent page not found in this workspace")
    position = await repo.max_sibling_position(s, workspace_id, parent_id) + 1.0
    page = Page(
        workspace_id=workspace_id,
        parent_id=parent_id,
        title=title,
        content_md=content_md,
        is_folder=is_folder,
        status=status,
        visibility=visibility,
        position=position,
        owner_id=user.id,
        created_by=user.id,
        updated_by=user.id,
    )
    s.add(page)
    await s.flush()
    await repo.add_version(s, page, user.id, summary="Created")
    await audit.record(
        s, workspace_id=workspace_id, actor_id=user.id, action="page.create",
        target_type="page", target_id=page.id, target_title=page.title,
    )
    return page


async def apply_update(
    s: AsyncSession, user: User, page: Page, fields: dict
) -> tuple[bool, bool]:
    """Apply editable fields; returns (content_changed, title_changed).
    Caller (orchestration) is responsible for reindexing and versioning."""
    content_changed = False
    title_changed = False

    if (title := fields.get("title")) is not None and title.strip() != page.title:
        if not title.strip():
            raise ValidationFailedError("Title is required")
        page.title = title.strip()
        title_changed = True
    if (content := fields.get("content_md")) is not None and content != page.content_md:
        page.content_md = content
        content_changed = True
    if "parent_id" in fields:
        new_parent = fields["parent_id"]
        if new_parent != page.parent_id:
            if new_parent is not None:
                parent = await repo.get(s, new_parent)
                if parent is None or parent.workspace_id != page.workspace_id:
                    raise ValidationFailedError("Parent page not found in this workspace")
                if await repo.is_descendant(s, page.id, new_parent):
                    raise ValidationFailedError("Cannot move a page into its own subtree")
            page.parent_id = new_parent
            page.position = await repo.max_sibling_position(s, page.workspace_id, new_parent) + 1.0
    if (position := fields.get("position")) is not None:
        page.position = float(position)
    for key in ("icon", "status", "visibility", "is_folder"):
        if fields.get(key) is not None:
            setattr(page, key, fields[key])
    if "owner_id" in fields and fields["owner_id"] is not None:
        page.owner_id = fields["owner_id"]

    if (tags := fields.get("tags")) is not None:
        await repo.set_page_tags(s, page, tags)
    if (metadata := fields.get("metadata")) is not None:
        await repo.set_page_metadata(s, page.id, {k: str(v) for k, v in metadata.items()})

    page.updated_by = user.id
    return content_changed, title_changed


async def delete(s: AsyncSession, user: User, page: Page) -> None:
    await policy.require_page_edit(s, user, page)
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="page.delete",
        target_type="page", target_id=page.id, target_title=page.title,
    )
    await s.delete(page)
    await s.flush()


async def list_versions(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[PageVersion]:
    await get_for_read(s, user, page_id)
    return await repo.list_versions(s, page_id)


async def get_version(
    s: AsyncSession, user: User, page_id: uuid.UUID, version_id: uuid.UUID
) -> PageVersion:
    await get_for_read(s, user, page_id)
    version = await repo.get_version(s, page_id, version_id)
    if version is None:
        raise NotFoundError("Version not found")
    return version


async def list_shares(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[PageShare]:
    await get_for_read(s, user, page_id)
    return await repo.list_shares(s, page_id)


async def add_share(s: AsyncSession, user: User, page_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
    page = await get_for_edit(s, user, page_id)
    if await policy.role_in_workspace(s, await _user(s, target_user_id), page.workspace_id) is None:
        raise ValidationFailedError("User is not a member of this workspace")
    await repo.add_share(s, page_id, target_user_id)
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="page.share",
        target_type="page", target_id=page.id, target_title=page.title,
        detail={"user_id": str(target_user_id)},
    )


async def remove_share(s: AsyncSession, user: User, page_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
    page = await get_for_edit(s, user, page_id)
    await repo.remove_share(s, page_id, target_user_id)
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="page.unshare",
        target_type="page", target_id=page.id, target_title=page.title,
        detail={"user_id": str(target_user_id)},
    )


async def _user(s: AsyncSession, user_id: uuid.UUID) -> User:
    user = await s.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user
