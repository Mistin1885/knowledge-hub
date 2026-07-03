"""Central RBAC checks. Every service that touches workspace data goes through here."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageShare, User
from app.modules.workspaces.infra import repo
from app.shared.constants import (
    PERMISSION_MIN_ROLE,
    ROLE_RANK,
    PageVisibility,
    Permission,
    Role,
)
from app.shared.exceptions import NotFoundError, PermissionDeniedError


async def role_in_workspace(s: AsyncSession, user: User, workspace_id: uuid.UUID) -> Role | None:
    member = await repo.get_member(s, workspace_id, user.id)
    return Role(member.role) if member else None


def role_has(role: Role | None, permission: Permission) -> bool:
    return role is not None and ROLE_RANK[role] >= ROLE_RANK[PERMISSION_MIN_ROLE[permission]]


async def require_permission(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, permission: Permission
) -> Role:
    """Single gate for workspace access. No membership -> the workspace does
    not exist for this user (404); insufficient permission -> 403."""
    role = await role_in_workspace(s, user, workspace_id)
    if role is None:
        # hide existence from non-members
        raise NotFoundError("Workspace not found")
    if not role_has(role, permission):
        raise PermissionDeniedError(f"Requires {permission} permission on this workspace")
    return role


async def can_read_page(s: AsyncSession, user: User, page: Page) -> bool:
    role = await role_in_workspace(s, user, page.workspace_id)
    if role is None:
        return False
    if page.visibility == PageVisibility.PRIVATE:
        if page.created_by == user.id or page.owner_id == user.id:
            return True
        share = await s.scalar(
            select(PageShare).where(PageShare.page_id == page.id, PageShare.user_id == user.id)
        )
        return share is not None
    return True


async def require_page_read(s: AsyncSession, user: User, page: Page) -> None:
    if not await can_read_page(s, user, page):
        raise NotFoundError("Page not found")


async def require_page_edit(s: AsyncSession, user: User, page: Page) -> None:
    await require_page_read(s, user, page)
    role = await role_in_workspace(s, user, page.workspace_id)
    if not role_has(role, Permission.WRITE):
        raise PermissionDeniedError("You have read-only access to this workspace")


def visible_pages_filter(user_id: uuid.UUID):
    """SQL filter: pages the user may see inside a workspace they belong to."""
    from sqlalchemy import exists, or_

    return or_(
        Page.visibility == PageVisibility.WORKSPACE,
        Page.created_by == user_id,
        Page.owner_id == user_id,
        exists(select(1).where(PageShare.page_id == Page.id, PageShare.user_id == user_id)),
    )
