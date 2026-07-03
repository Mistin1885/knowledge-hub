import uuid

from fastapi import APIRouter, Query

from app.api import serializers
from app.api.deps import DB, CurrentUser
from app.api.schemas.links import (
    BacklinkOut,
    GraphOut,
    LinksOut,
    OutgoingLinkOut,
    RelatedOut,
)
from app.api.schemas.pages import PageOut
from app.modules.links.services import graph as graph_service
from app.modules.links.services import links as links_service
from app.modules.links.services import related as related_service

router = APIRouter(tags=["links"])


@router.get("/pages/{page_id}/backlinks", response_model=list[BacklinkOut])
async def backlinks(page_id: uuid.UUID, user: CurrentUser, s: DB):
    items = await links_service.backlinks(s, user, page_id)
    return [
        BacklinkOut(page=await serializers.page_out(s, item["page"]), context=item["context"])
        for item in items
    ]


@router.get("/pages/{page_id}/links", response_model=LinksOut)
async def outgoing_links(page_id: uuid.UUID, user: CurrentUser, s: DB):
    items = await links_service.outgoing(s, user, page_id)
    return LinksOut(
        outgoing=[
            OutgoingLinkOut(
                page=await serializers.page_out(s, item["page"]) if item["page"] else None,
                target_title=item["target_title"],
                resolved=item["resolved"],
                context=item["context"],
            )
            for item in items
        ]
    )


@router.get("/pages/{page_id}/related", response_model=list[RelatedOut])
async def related(page_id: uuid.UUID, user: CurrentUser, s: DB, limit: int = Query(10, le=50)):
    items = await related_service.related_pages(s, user, page_id, limit=limit)
    return [
        RelatedOut(
            page=await serializers.page_out(s, item["page"]),
            score=item["score"],
            reasons=item["reasons"],
        )
        for item in items
    ]


@router.get("/pages/{page_id}/mentions", response_model=list[BacklinkOut])
async def unlinked_mentions(page_id: uuid.UUID, user: CurrentUser, s: DB):
    items = await links_service.unlinked_mentions(s, user, page_id)
    return [
        BacklinkOut(page=await serializers.page_out(s, item["page"]), context=item["context"])
        for item in items
    ]


@router.get("/workspaces/{workspace_id}/graph", response_model=GraphOut)
async def workspace_graph(
    workspace_id: uuid.UUID, user: CurrentUser, s: DB, tags: int = Query(1)
):
    return await graph_service.workspace_graph(s, user, workspace_id, include_tags=bool(tags))


@router.get("/workspaces/{workspace_id}/orphans", response_model=list[PageOut])
async def orphans(workspace_id: uuid.UUID, user: CurrentUser, s: DB):
    pages = await links_service.orphans(s, user, workspace_id)
    return [await serializers.page_out(s, p) for p in pages]


@router.get("/workspaces/{workspace_id}/resolve", response_model=PageOut | None)
async def resolve_title(workspace_id: uuid.UUID, title: str, user: CurrentUser, s: DB):
    page = await links_service.resolve_title_to_page(s, user, workspace_id, title)
    return await serializers.page_out(s, page) if page else None
