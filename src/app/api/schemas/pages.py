import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.common import ORMModel, UserRef
from app.shared.constants import PageStatus, PageVisibility


class PageCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    parent_id: uuid.UUID | None = None
    content_md: str = ""
    is_folder: bool = False
    status: PageStatus = PageStatus.PUBLISHED
    visibility: PageVisibility = PageVisibility.WORKSPACE
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class PageUpdateIn(BaseModel):
    # tri-state PATCH: absent fields untouched (model_fields_set)
    title: str | None = Field(default=None, max_length=500)
    content_md: str | None = None
    parent_id: uuid.UUID | None = None
    position: float | None = None
    icon: str | None = Field(default=None, max_length=16)
    status: PageStatus | None = None
    visibility: PageVisibility | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    owner_id: uuid.UUID | None = None
    is_folder: bool | None = None


class PageOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str
    icon: str | None
    status: str
    visibility: str
    position: float
    is_folder: bool
    owner: UserRef | None
    tags: list[str]
    metadata: dict[str, str]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PageDetailOut(PageOut):
    content_md: str
    backlink_count: int
    outgoing_count: int


class ChildPageOut(BaseModel):
    page: PageOut
    preview: str


class VersionOut(ORMModel):
    id: uuid.UUID
    version: int
    title: str
    author: UserRef | None
    summary: str | None
    created_at: datetime


class VersionDetailOut(VersionOut):
    content_md: str


class CommentIn(BaseModel):
    body_md: str = Field(min_length=1)
    anchor: str | None = None


class CommentUpdateIn(BaseModel):
    body_md: str | None = None
    resolved: bool | None = None


class CommentOut(BaseModel):
    id: uuid.UUID
    author: UserRef | None
    body_md: str
    anchor: str | None
    resolved: bool
    created_at: datetime
    updated_at: datetime
    mentions: list[UserRef]


class MentionOut(BaseModel):
    comment_id: uuid.UUID
    page_id: uuid.UUID
    page_title: str
    author: UserRef
    body_md: str
    created_at: datetime
    read: bool


class AttachmentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    url: str


class ShareOut(BaseModel):
    user_id: uuid.UUID
    name: str


class ShareIn(BaseModel):
    user_id: uuid.UUID


class TagOut(BaseModel):
    name: str
    page_count: int


class MetadataKeyOut(BaseModel):
    key: str
    values: list[str]
