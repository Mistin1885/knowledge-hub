import uuid

from pydantic import BaseModel, Field

from app.api.schemas.pages import PageOut


class SnippetOut(BaseModel):
    text: str
    heading: str | None


class SearchResultOut(BaseModel):
    page: PageOut
    score: float
    snippets: list[SnippetOut]


class SearchOut(BaseModel):
    results: list[SearchResultOut]
    mode_used: str


class AskIn(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=30)


class ChunkPageRef(BaseModel):
    id: uuid.UUID
    title: str


class ChunkOut(BaseModel):
    page: ChunkPageRef
    heading: str | None
    text: str
    score: float


class AskOut(BaseModel):
    chunks: list[ChunkOut]
