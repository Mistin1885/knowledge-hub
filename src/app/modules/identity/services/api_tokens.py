import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import ApiToken
from app.modules.identity.domain import tokens as token_policy
from app.modules.identity.infra import repo
from app.shared.exceptions import NotFoundError
from app.shared.utils import new_token, sha256_hex


async def create(s: AsyncSession, user_id: uuid.UUID, name: str) -> tuple[ApiToken, str]:
    """Returns (token row, raw token). Raw token is shown to the user exactly once."""
    raw = new_token(token_policy.API_TOKEN_PREFIX)
    row = await repo.create_api_token(
        s,
        user_id=user_id,
        name=name,
        prefix=token_policy.token_display_prefix(raw),
        token_hash=sha256_hex(raw),
    )
    return row, raw


async def list_for_user(s: AsyncSession, user_id: uuid.UUID) -> list[ApiToken]:
    return await repo.list_api_tokens(s, user_id)


async def revoke(s: AsyncSession, user_id: uuid.UUID, token_id: uuid.UUID) -> None:
    if not await repo.delete_api_token(s, user_id, token_id):
        raise NotFoundError("Token not found")
