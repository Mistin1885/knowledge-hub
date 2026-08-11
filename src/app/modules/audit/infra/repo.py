import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infra.db.models import AuditLog


async def list_for_workspace(
    s: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int = 50,
    before: datetime | None = None,
    offset: int = 0,
) -> list[AuditLog]:
    q = (
        select(AuditLog)
        .options(joinedload(AuditLog.actor))
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if before is not None:
        q = q.where(AuditLog.created_at < before)
    return list(await s.scalars(q))


async def count_for_workspace(s: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await s.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.workspace_id == workspace_id)
        )
    ) or 0
