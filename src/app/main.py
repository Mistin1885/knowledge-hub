import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    attachments,
    auth,
    collab,
    comments,
    links,
    pages,
    search,
    workspaces,
)
from app.infra.db.engine import db_session, engine
from app.mcpserver.server import mcp as mcp_server
from app.modules.collab.services import rooms
from app.orchestration import index_page as pipeline
from app.shared.config.settings import settings
from app.shared.exceptions import AppError
from app.shared.logging import setup_logging


async def _collab_snapshot(
    page_id: uuid.UUID, content_md: str, editor_ids: list[uuid.UUID], create_version: bool
) -> None:
    async with db_session() as s:
        await pipeline.snapshot_from_collab(
            s, page_id, content_md, editor_ids, create_version=create_version
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    rooms.manager.configure(on_snapshot=_collab_snapshot)
    async with mcp_server.session_manager.run():
        yield
        # flush any open collaboration sessions before shutdown
        for room in list(rooms.manager.rooms.values()):
            await rooms.manager._persist(room, create_version=True)
    await engine.dispose()


app = FastAPI(title="Knowledge Hub", version="1.0.0", lifespan=lifespan)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


API_PREFIX = "/api/v1"
for router in (
    auth.router,
    workspaces.router,
    pages.router,
    comments.router,
    attachments.router,
    links.router,
    search.router,
):
    app.include_router(router, prefix=API_PREFIX)

app.include_router(collab.router, prefix=API_PREFIX)
# WebSocket lives outside /api/v1 per contract (WS /collab/{page_id})
app.include_router(collab.ws_router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


# MCP endpoint for AI agents: POST /mcp (streamable HTTP transport)
app.mount("/mcp", mcp_server.streamable_http_app())


@app.api_route("/mcp", methods=["POST", "GET", "DELETE"], include_in_schema=False)
async def mcp_no_slash():
    # the transport lives at /mcp/ inside the mount; 307 keeps method + body
    return RedirectResponse("/mcp/", status_code=307)


# --- SPA (production: serve the built frontend) ------------------------------

if settings.frontend_dist.is_dir():
    assets = settings.frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = settings.frontend_dist / path
        if path and ".." not in path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist / "index.html")
