import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import AuditLog


async def record(
    s: AsyncSession,
    *,
    workspace_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    target_title: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    s.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_title=target_title,
            detail=detail,
        )
    )
