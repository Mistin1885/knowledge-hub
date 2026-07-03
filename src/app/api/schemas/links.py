from pydantic import BaseModel

from app.api.schemas.pages import PageOut


class BacklinkOut(BaseModel):
    page: PageOut
    context: str | None


class OutgoingLinkOut(BaseModel):
    page: PageOut | None
    target_title: str
    resolved: bool
    context: str | None


class LinksOut(BaseModel):
    outgoing: list[OutgoingLinkOut]


class RelatedOut(BaseModel):
    page: PageOut
    score: float
    reasons: list[str]


class GraphNodeOut(BaseModel):
    id: str
    title: str
    icon: str | None
    status: str | None
    is_tag: bool
    link_count: int


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    kind: str


class GraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
