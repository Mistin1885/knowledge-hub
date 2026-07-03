import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Page, PageYDoc


async def load_state(s: AsyncSession, page_id: uuid.UUID) -> bytes | None:
    row = await s.get(PageYDoc, page_id)
    return bytes(row.state) if row else None


async def save_state(s: AsyncSession, page_id: uuid.UUID, state: bytes) -> None:
    row = await s.get(PageYDoc, page_id)
    if row is None:
        s.add(PageYDoc(page_id=page_id, state=state))
    else:
        row.state = state


async def get_page(s: AsyncSession, page_id: uuid.UUID) -> Page | None:
    return await s.get(Page, page_id)
