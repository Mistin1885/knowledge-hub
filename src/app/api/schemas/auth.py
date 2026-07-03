import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.api.schemas.common import ORMModel


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TokenOut(ORMModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class TokenCreatedOut(BaseModel):
    id: uuid.UUID
    name: str
    token: str
