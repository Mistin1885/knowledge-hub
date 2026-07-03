"""MCP server exposing the knowledge base to AI agents (read-only v1).

Auth: `Authorization: Bearer kmt_...` header (HTTP transport) or the
KM_MCP_TOKEN env var (stdio transport). All RBAC is enforced by the same
service layer the web API uses.
"""

import os
import uuid
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from app.infra.db.engine import db_session
from app.infra.db.models import Page, User
from app.modules.identity.services import accounts
from app.modules.links.services import links as links_service
from app.modules.links.services import related as related_service
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import pages as pages_service
from app.modules.search.services import search as search_service
from app.modules.workspaces.infra import repo as ws_repo
from app.modules.workspaces.services import workspaces as ws_service
from app.shared.exceptions import AppError, UnauthenticatedError

mcp = FastMCP(
    "knowledge-hub",
    instructions=(
        "Company knowledge base. Use search_pages/ask to find information, "
        "get_page to read a document, get_backlinks/get_related_pages to explore "
        "context. Cite page titles and ids when answering from these sources."
    ),
    stateless_http=True,
    streamable_http_path="/",  # mounted at /mcp by app.main
)


async def _current_user(s, ctx: Context | None) -> User:
    token: str | None = None
    if ctx is not None:
        try:
            request = ctx.request_context.request
            header = request.headers.get("authorization", "") if request else ""
            if header.lower().startswith("bearer "):
                token = header[7:].strip()
        except (AttributeError, ValueError):
            token = None
    if token is None:
        token = os.environ.get("KM_MCP_TOKEN")
    if not token:
        raise UnauthenticatedError(
            "No API token: send 'Authorization: Bearer kmt_...' or set KM_MCP_TOKEN"
        )
    user = await accounts.authenticate_api_token(s, token)
    if user is None:
        raise UnauthenticatedError("Invalid API token")
    return user


async def _workspace(s, user: User, slug: str):
    ws = await ws_repo.get_by_slug(s, slug)
    if ws is None:
        raise AppError(f"Workspace '{slug}' not found")
    await ws_service.get_for_user(s, user, ws.id)  # raises if not a member
    return ws


def _page_brief(page: Page) -> dict[str, Any]:
    return {
        "id": str(page.id),
        "title": page.title,
        "status": page.status,
        "updated_at": page.updated_at.isoformat(),
    }


async def _page_full(s, page: Page) -> dict[str, Any]:
    return {
        **_page_brief(page),
        "workspace_id": str(page.workspace_id),
        "tags": await pages_repo.get_page_tags(s, page.id),
        "metadata": await pages_repo.get_page_metadata(s, page.id),
        "content_md": page.content_md,
    }


@mcp.tool()
async def list_workspaces(ctx: Context) -> list[dict]:
    """List knowledge-base workspaces you can access (returns slug, name, description)."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        return [
            {"slug": ws.slug, "name": ws.name, "description": ws.description, "role": role}
            for ws, role in await ws_service.list_mine(s, user)
        ]


@mcp.tool()
async def search_pages(
    ctx: Context,
    workspace: str,
    query: str,
    tags: list[str] | None = None,
    mode: str = "hybrid",
    limit: int = 10,
) -> list[dict]:
    """Search pages in a workspace. mode: hybrid | fulltext | semantic.
    Returns pages with relevance scores and matching snippets."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        ws = await _workspace(s, user, workspace)
        result = await search_service.search(
            s, user, ws.id, query, tags=tags or [], mode=mode, limit=min(limit, 30)
        )
        return [
            {
                "page": _page_brief(item["page"]),
                "score": item["score"],
                "snippets": item["snippets"],
            }
            for item in result["results"]
        ]


@mcp.tool()
async def ask(ctx: Context, workspace: str, question: str, limit: int = 8) -> dict:
    """Retrieve the most relevant content chunks for a question, with source pages —
    use these as citations when answering."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        ws = await _workspace(s, user, workspace)
        result = await search_service.ask(s, user, ws.id, question, limit=min(limit, 20))
        for chunk in result["chunks"]:
            chunk["page"]["id"] = str(chunk["page"]["id"])
        return result


@mcp.tool()
async def get_page(ctx: Context, page_id: str = "", workspace: str = "", title: str = "") -> dict:
    """Read a page's full markdown content plus tags and metadata.
    Provide either page_id, or workspace slug + title."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        if page_id:
            page = await pages_service.get_for_read(s, user, uuid.UUID(page_id))
        elif workspace and title:
            ws = await _workspace(s, user, workspace)
            page = await links_service.resolve_title_to_page(s, user, ws.id, title)
            if page is None:
                raise AppError(f"No page titled '{title}' in workspace '{workspace}'")
        else:
            raise AppError("Provide page_id, or workspace and title")
        return await _page_full(s, page)


@mcp.tool()
async def get_backlinks(ctx: Context, page_id: str) -> list[dict]:
    """Pages that link TO this page, with the line of context around each link."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        items = await links_service.backlinks(s, user, uuid.UUID(page_id))
        return [{"page": _page_brief(i["page"]), "context": i["context"]} for i in items]


@mcp.tool()
async def get_outgoing_links(ctx: Context, page_id: str) -> list[dict]:
    """Pages this page links to (resolved and unresolved wikilinks)."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        items = await links_service.outgoing(s, user, uuid.UUID(page_id))
        return [
            {
                "target_title": i["target_title"],
                "resolved": i["resolved"],
                "page": _page_brief(i["page"]) if i["page"] else None,
                "context": i["context"],
            }
            for i in items
        ]


@mcp.tool()
async def get_related_pages(ctx: Context, page_id: str, limit: int = 10) -> list[dict]:
    """Pages related to this one via links, shared tags, and semantic similarity."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        items = await related_service.related_pages(s, user, uuid.UUID(page_id), limit=limit)
        return [
            {"page": _page_brief(i["page"]), "score": i["score"], "reasons": i["reasons"]}
            for i in items
        ]


@mcp.tool()
async def list_tags(ctx: Context, workspace: str) -> list[dict]:
    """All tags in a workspace with page counts."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        ws = await _workspace(s, user, workspace)
        return [
            {"name": name, "page_count": count}
            for name, count in await pages_repo.list_workspace_tags(s, ws.id)
        ]


@mcp.tool()
async def list_pages_by_tag(ctx: Context, workspace: str, tag: str) -> list[dict]:
    """Pages carrying a given tag."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        ws = await _workspace(s, user, workspace)
        result = await search_service.search(s, user, ws.id, "", tags=[tag], limit=100)
        return [_page_brief(item["page"]) for item in result["results"]]


@mcp.tool()
async def get_page_context(ctx: Context, page_id: str) -> dict:
    """A page plus its knowledge-graph neighborhood: backlinks, outgoing links,
    related pages, tags and metadata — everything needed to understand it in context."""
    async with db_session() as s:
        user = await _current_user(s, ctx)
        pid = uuid.UUID(page_id)
        page = await pages_service.get_for_read(s, user, pid)
        backlinks = await links_service.backlinks(s, user, pid)
        outgoing = await links_service.outgoing(s, user, pid)
        related = await related_service.related_pages(s, user, pid, limit=8)
        return {
            "page": await _page_full(s, page),
            "backlinks": [{"page": _page_brief(i["page"]), "context": i["context"]} for i in backlinks],
            "outgoing": [
                {"target_title": i["target_title"], "resolved": i["resolved"]} for i in outgoing
            ],
            "related": [
                {"page": _page_brief(i["page"]), "reasons": i["reasons"]} for i in related
            ],
        }
