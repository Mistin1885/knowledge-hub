import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import User, Workspace, WorkspaceMember
from app.modules.audit.services import audit
from app.modules.workspaces.infra import repo
from app.modules.workspaces.services import policy
from app.shared.constants import Role
from app.shared.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.shared.utils import slugify


async def create(
    s: AsyncSession,
    user: User,
    name: str,
    slug: str | None = None,
    description: str | None = None,
    icon: str | None = None,
) -> tuple[Workspace, Role]:
    slug = slugify(slug or name)
    if await repo.slug_taken(s, slug):
        raise ConflictError(f"Workspace slug '{slug}' is taken")
    ws = await repo.create(s, name=name, slug=slug, description=description, icon=icon)
    await repo.add_member(s, ws.id, user.id, Role.OWNER)
    await audit.record(
        s, workspace_id=ws.id, actor_id=user.id, action="workspace.create",
        target_type="workspace", target_id=ws.id, target_title=ws.name,
    )
    return ws, Role.OWNER


async def list_mine(s: AsyncSession, user: User) -> list[tuple[Workspace, str]]:
    return await repo.list_for_user(s, user.id)


async def get_for_user(s: AsyncSession, user: User, workspace_id: uuid.UUID) -> tuple[Workspace, Role]:
    role = await policy.require_role(s, user, workspace_id, Role.VIEWER)
    ws = await repo.get(s, workspace_id)
    if ws is None:
        raise NotFoundError("Workspace not found")
    return ws, role


async def update(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, **fields
) -> tuple[Workspace, Role]:
    role = await policy.require_role(s, user, workspace_id, Role.ADMIN)
    ws = await repo.get(s, workspace_id)
    if ws is None:
        raise NotFoundError("Workspace not found")
    for key in ("name", "description", "icon"):
        if fields.get(key) is not None:
            setattr(ws, key, fields[key])
    await audit.record(
        s, workspace_id=ws.id, actor_id=user.id, action="workspace.update",
        target_type="workspace", target_id=ws.id, target_title=ws.name,
    )
    return ws, role


async def delete(s: AsyncSession, user: User, workspace_id: uuid.UUID) -> None:
    await policy.require_role(s, user, workspace_id, Role.OWNER)
    ws = await repo.get(s, workspace_id)
    if ws is None:
        raise NotFoundError("Workspace not found")
    await audit.record(
        s, workspace_id=None, actor_id=user.id, action="workspace.delete",
        target_type="workspace", target_id=ws.id, target_title=ws.name,
    )
    await repo.delete_workspace(s, workspace_id)


async def list_members(
    s: AsyncSession, user: User, workspace_id: uuid.UUID
) -> list[WorkspaceMember]:
    await policy.require_role(s, user, workspace_id, Role.VIEWER)
    return await repo.list_members(s, workspace_id)


async def add_member(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, email: str, role: Role
) -> WorkspaceMember:
    await policy.require_role(s, user, workspace_id, Role.ADMIN)
    if role == Role.OWNER:
        await policy.require_role(s, user, workspace_id, Role.OWNER)
    target = await repo.get_user_by_email(s, email)
    if target is None:
        raise NotFoundError(f"No user with email {email} — they must register first")
    if await repo.get_member(s, workspace_id, target.id):
        raise ConflictError("Already a member")
    member = await repo.add_member(s, workspace_id, target.id, role)
    await audit.record(
        s, workspace_id=workspace_id, actor_id=user.id, action="member.add",
        target_type="user", target_id=target.id, target_title=target.name,
        detail={"role": str(role)},
    )
    return member


async def change_role(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, target_user_id: uuid.UUID, role: Role
) -> WorkspaceMember:
    await policy.require_role(s, user, workspace_id, Role.ADMIN)
    member = await repo.get_member(s, workspace_id, target_user_id)
    if member is None:
        raise NotFoundError("Member not found")
    if role == Role.OWNER or member.role == Role.OWNER:
        await policy.require_role(s, user, workspace_id, Role.OWNER)
    if member.role == Role.OWNER and role != Role.OWNER:
        if await repo.count_owners(s, workspace_id) <= 1:
            raise ValidationFailedError("Workspace must keep at least one owner")
    member.role = role
    await audit.record(
        s, workspace_id=workspace_id, actor_id=user.id, action="member.change_role",
        target_type="user", target_id=target_user_id, detail={"role": str(role)},
    )
    return member


async def remove_member(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, target_user_id: uuid.UUID
) -> None:
    if user.id != target_user_id:  # self-leave is always allowed
        await policy.require_role(s, user, workspace_id, Role.ADMIN)
    member = await repo.get_member(s, workspace_id, target_user_id)
    if member is None:
        raise NotFoundError("Member not found")
    if member.role == Role.OWNER and await repo.count_owners(s, workspace_id) <= 1:
        raise ValidationFailedError("Workspace must keep at least one owner")
    await repo.remove_member(s, workspace_id, target_user_id)
    await audit.record(
        s, workspace_id=workspace_id, actor_id=user.id, action="member.remove",
        target_type="user", target_id=target_user_id,
    )
