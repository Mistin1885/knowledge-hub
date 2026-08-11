import uuid

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infra.db.models import User, Workspace, WorkspaceMember


async def get(s: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    return await s.get(Workspace, workspace_id)


async def get_by_slug(s: AsyncSession, slug: str) -> Workspace | None:
    return await s.scalar(select(Workspace).where(Workspace.slug == slug))


async def slug_taken(s: AsyncSession, slug: str) -> bool:
    return await s.scalar(select(func.count()).where(Workspace.slug == slug)) > 0


async def create(
    s: AsyncSession, name: str, slug: str, description: str | None, icon: str | None
) -> Workspace:
    ws = Workspace(name=name, slug=slug, description=description, icon=icon)
    s.add(ws)
    await s.flush()
    return ws


async def delete_workspace(s: AsyncSession, workspace_id: uuid.UUID) -> None:
    ws = await s.get(Workspace, workspace_id)
    if ws is not None:
        await s.delete(ws)


async def list_for_user(s: AsyncSession, user_id: uuid.UUID) -> list[tuple[Workspace, str]]:
    rows = await s.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.created_at)
    )
    return [(w, r) for w, r in rows]


async def get_member(
    s: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    return await s.get(WorkspaceMember, (workspace_id, user_id))


async def list_members(s: AsyncSession, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
    return list(
        await s.scalars(
            select(WorkspaceMember)
            .options(joinedload(WorkspaceMember.user))
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at)
        )
    )


async def list_user_directory(
    s: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    offset: int,
    limit: int,
) -> tuple[list[tuple[User, WorkspaceMember | None]], int]:
    """All registered users with their optional membership in one workspace."""
    membership = WorkspaceMember
    join_condition = and_(
        membership.user_id == User.id,
        membership.workspace_id == workspace_id,
    )
    total = (await s.scalar(select(func.count(User.id)))) or 0
    rows = await s.execute(
        select(User, membership)
        .outerjoin(membership, join_condition)
        .order_by(
            case(
                (membership.role == "owner", 0),
                (membership.role.is_not(None), 1),
                else_=2,
            ),
            func.lower(User.name),
            func.lower(User.email),
            User.id,
        )
        .offset(offset)
        .limit(limit)
    )
    return [(row[0], row[1]) for row in rows], total


async def add_member(
    s: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> WorkspaceMember:
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
    s.add(member)
    await s.flush()
    return member


async def remove_member(s: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await s.execute(
        delete(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
    )


async def count_owners(s: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await s.scalar(
            select(func.count()).where(
                WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.role == "owner"
            )
        )
    ) or 0


async def get_user_by_email(s: AsyncSession, email: str) -> User | None:
    return await s.scalar(select(User).where(func.lower(User.email) == email.lower()))
