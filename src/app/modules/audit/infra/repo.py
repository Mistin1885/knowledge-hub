import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infra.db.models import AuditLog


async def list_for_workspace(
    s: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int = 50,
    before: datetime | None = None,
) -> list[AuditLog]:
    q = (
        select(AuditLog)
        .options(joinedload(AuditLog.actor))
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    if before is not None:
        q = q.where(AuditLog.created_at < before)
    return list(await s.scalars(q))
