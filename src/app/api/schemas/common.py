import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRef(ORMModel):
    id: uuid.UUID
    name: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    is_admin: bool
    created_at: datetime
