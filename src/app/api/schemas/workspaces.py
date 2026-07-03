import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.common import ORMModel, UserRef
from app.shared.constants import Role


class WorkspaceCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=16)


class WorkspaceUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=16)


class WorkspaceOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    icon: str | None
    created_at: datetime
    my_role: Role


class MemberAddIn(BaseModel):
    email: str
    role: Role = Role.MEMBER


class MemberUpdateIn(BaseModel):
    role: Role


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: Role
    joined_at: datetime


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    actor: UserRef | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    target_title: str | None
    detail: dict[str, Any] | None
    created_at: datetime


class AuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    next_cursor: str | None
