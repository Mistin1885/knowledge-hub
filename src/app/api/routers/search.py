import uuid

from fastapi import APIRouter, Query, Request

from app.api import serializers
from app.api.deps import DB, CurrentUser
from app.api.schemas.search import AskIn, AskOut, SearchOut, SearchResultOut, SnippetOut
from app.modules.search.services import search as search_service

router = APIRouter(tags=["search"])


@router.get("/workspaces/{workspace_id}/search", response_model=SearchOut)
async def search(
    workspace_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    s: DB,
    q: str = "",
    tags: str = "",
    status: str | None = None,
    owner_id: uuid.UUID | None = None,
    mode: str = Query("hybrid", pattern="^(hybrid|fulltext|semantic)$"),
    limit: int = Query(20, le=100),
):
    metadata = {
        key[5:]: value
        for key, value in request.query_params.items()
        if key.startswith("meta.") and len(key) > 5
    }
    result = await search_service.search(
        s, user, workspace_id, q,
        tags=[t for t in tags.split(",") if t.strip()],
        status=status, owner_id=owner_id, metadata=metadata, mode=mode, limit=limit,
    )
    return SearchOut(
        results=[
            SearchResultOut(
                page=await serializers.page_out(s, item["page"]),
                score=item["score"],
                snippets=[SnippetOut(**sn) for sn in item["snippets"]],
            )
            for item in result["results"]
        ],
        mode_used=result["mode_used"],
    )


@router.post("/workspaces/{workspace_id}/ask", response_model=AskOut)
async def ask(workspace_id: uuid.UUID, body: AskIn, user: CurrentUser, s: DB):
    return await search_service.ask(s, user, workspace_id, body.question, limit=body.limit)
