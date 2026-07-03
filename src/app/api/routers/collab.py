import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import DB, CurrentUser, websocket_user
from app.infra.db.engine import session_factory
from app.modules.collab.services import rooms
from app.modules.pages.infra import repo as pages_repo
from app.modules.workspaces.services import policy
from app.shared.constants import Permission
from app.shared.utils import stable_color

router = APIRouter(tags=["collab"])  # REST endpoints under /api/v1
ws_router = APIRouter()  # WebSocket at root path per contract

WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN = 4403


@ws_router.websocket("/collab/{page_id}")
async def collab_socket(ws: WebSocket, page_id: uuid.UUID):
    await ws.accept()
    async with session_factory() as s:
        user = await websocket_user(ws, s)
        if user is None:
            await ws.close(code=WS_UNAUTHENTICATED)
            return
        page = await pages_repo.get(s, page_id)
        if page is None or not await policy.can_read_page(s, user, page):
            await ws.close(code=WS_FORBIDDEN)
            return
        role = await policy.role_in_workspace(s, user, page.workspace_id)
        can_edit = policy.role_has(role, Permission.WRITE)
        await s.commit()

    display = {"name": user.name, "color": stable_color(str(user.id))}
    room = await rooms.manager.connect(page_id, ws, user.id, can_edit, display)
    try:
        while True:
            data = await ws.receive_bytes()
            await rooms.manager.handle_message(room, ws, data)
    except WebSocketDisconnect:
        pass
    finally:
        await rooms.manager.disconnect(room, ws)


@router.get("/pages/{page_id}/presence")
async def presence(page_id: uuid.UUID, user: CurrentUser, s: DB):
    from app.modules.pages.services import pages as pages_service

    await pages_service.get_for_read(s, user, page_id)
    return rooms.manager.presence(page_id)
