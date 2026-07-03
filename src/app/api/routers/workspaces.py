import uuid
from datetime import datetime

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.api.schemas.workspaces import (
    AuditEntryOut,
    AuditPageOut,
    MemberAddIn,
    MemberOut,
    MemberUpdateIn,
    WorkspaceCreateIn,
    WorkspaceOut,
    WorkspaceUpdateIn,
)
from app.modules.audit.infra import repo as audit_repo
from app.modules.pages.services import export as export_service
from app.modules.workspaces.services import policy, workspaces
from app.shared.constants import Permission, Role, role_permissions
from app.shared.exceptions import ValidationFailedError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _ws_out(ws, role) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, description=ws.description,
        icon=ws.icon, created_at=ws.created_at, my_role=role,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(user: CurrentUser, s: DB):
    return [_ws_out(ws, role) for ws, role in await workspaces.list_mine(s, user)]


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceCreateIn, user: CurrentUser, s: DB):
    ws, role = await workspaces.create(
        s, user, body.name, body.slug, body.description, body.icon
    )
    return _ws_out(ws, role)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    ws, role = await workspaces.get_for_user(s, user, workspace_id)
    return _ws_out(ws, role)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: uuid.UUID, body: WorkspaceUpdateIn, user: CurrentUser, s: DB
):
    ws, role = await workspaces.update(s, user, workspace_id, **body.model_dump())
    return _ws_out(ws, role)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    await workspaces.delete(s, user, workspace_id)


@router.get("/{workspace_id}/export")
async def export_workspace(workspace_id: uuid.UUID, user: CurrentUser, s: DB) -> Response:
    """All pages the user can see, zipped with the folder structure preserved."""
    filename, data = await export_service.export_workspace(s, user, workspace_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": export_service.content_disposition(filename)},
    )


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
async def list_members(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    return [
        MemberOut(
            user_id=m.user_id, email=m.user.email, name=m.user.name,
            role=Role(m.role), permissions=role_permissions(Role(m.role)),
            joined_at=m.joined_at,
        )
        for m in await workspaces.list_members(s, user, workspace_id)
    ]


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(workspace_id: uuid.UUID, body: MemberAddIn, user: CurrentUser, s: DB):
    await workspaces.add_member(s, user, workspace_id, body.email, body.effective_role())
    return {"ok": True}


@router.patch("/{workspace_id}/members/{member_user_id}")
async def change_member_role(
    workspace_id: uuid.UUID, member_user_id: uuid.UUID, body: MemberUpdateIn,
    user: CurrentUser, s: DB,
):
    role = body.effective_role()
    if role is None:
        raise ValidationFailedError("Provide either 'role' or 'access' (read|write)")
    await workspaces.change_role(s, user, workspace_id, member_user_id, role)
    return {"ok": True}


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: uuid.UUID, member_user_id: uuid.UUID, user: CurrentUser, s: DB
):
    await workspaces.remove_member(s, user, workspace_id, member_user_id)


@router.get("/{workspace_id}/audit", response_model=AuditPageOut)
async def audit_log(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    s: DB,
    limit: int = Query(default=50, le=200),
    cursor: datetime | None = None,
):
    await policy.require_permission(s, user, workspace_id, Permission.MANAGE)
    entries = await audit_repo.list_for_workspace(s, workspace_id, limit=limit, before=cursor)
    items = [
        AuditEntryOut(
            id=e.id,
            actor={"id": e.actor.id, "name": e.actor.name} if e.actor else None,
            action=e.action, target_type=e.target_type, target_id=e.target_id,
            target_title=e.target_title, detail=e.detail, created_at=e.created_at,
        )
        for e in entries
    ]
    next_cursor = items[-1].created_at.isoformat() if len(items) == limit else None
    return AuditPageOut(items=items, next_cursor=next_cursor)
