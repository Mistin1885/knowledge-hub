"""Central RBAC checks. Every service that touches workspace data goes through here."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageShare, User
from app.modules.workspaces.infra import repo
from app.shared.constants import ROLE_RANK, PageVisibility, Role
from app.shared.exceptions import NotFoundError, PermissionDeniedError


async def role_in_workspace(s: AsyncSession, user: User, workspace_id: uuid.UUID) -> Role | None:
    member = await repo.get_member(s, workspace_id, user.id)
    return Role(member.role) if member else None


async def require_role(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, minimum: Role
) -> Role:
    role = await role_in_workspace(s, user, workspace_id)
    if role is None:
        # hide existence from non-members
        raise NotFoundError("Workspace not found")
    if ROLE_RANK[role] < ROLE_RANK[minimum]:
        raise PermissionDeniedError(f"Requires {minimum} role")
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
    if role is None or ROLE_RANK[role] < ROLE_RANK[Role.MEMBER]:
        raise PermissionDeniedError("Viewers cannot edit pages")


def visible_pages_filter(user_id: uuid.UUID):
    """SQL filter: pages the user may see inside a workspace they belong to."""
    from sqlalchemy import exists, or_

    return or_(
        Page.visibility == PageVisibility.WORKSPACE,
        Page.created_by == user_id,
        Page.owner_id == user_id,
        exists(select(1).where(PageShare.page_id == Page.id, PageShare.user_id == user_id)),
    )
