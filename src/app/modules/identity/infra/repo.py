import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import ApiToken, Session, User


async def get_user(s: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await s.get(User, user_id)


async def get_user_by_email(s: AsyncSession, email: str) -> User | None:
    return await s.scalar(select(User).where(func.lower(User.email) == email.lower()))


async def get_user_by_name(s: AsyncSession, name: str) -> User | None:
    return await s.scalar(select(User).where(func.lower(User.name) == name.lower()))


async def count_users(s: AsyncSession) -> int:
    return (await s.scalar(select(func.count(User.id)))) or 0


async def create_user(
    s: AsyncSession, email: str, name: str, password_hash: str, is_admin: bool
) -> User:
    user = User(email=email.lower(), name=name, password_hash=password_hash, is_admin=is_admin)
    s.add(user)
    await s.flush()
    return user


async def create_session(
    s: AsyncSession,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
) -> Session:
    sess = Session(
        user_id=user_id, token_hash=token_hash, expires_at=expires_at, user_agent=user_agent
    )
    s.add(sess)
    await s.flush()
    return sess


async def get_session_with_user(s: AsyncSession, token_hash: str) -> tuple[Session, User] | None:
    row = (
        await s.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(Session.token_hash == token_hash)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def delete_session(s: AsyncSession, token_hash: str) -> None:
    await s.execute(delete(Session).where(Session.token_hash == token_hash))


async def create_api_token(
    s: AsyncSession, user_id: uuid.UUID, name: str, prefix: str, token_hash: str
) -> ApiToken:
    token = ApiToken(user_id=user_id, name=name, prefix=prefix, token_hash=token_hash)
    s.add(token)
    await s.flush()
    return token


async def list_api_tokens(s: AsyncSession, user_id: uuid.UUID) -> list[ApiToken]:
    return list(
        await s.scalars(
            select(ApiToken).where(ApiToken.user_id == user_id).order_by(ApiToken.created_at)
        )
    )


async def delete_api_token(s: AsyncSession, user_id: uuid.UUID, token_id: uuid.UUID) -> bool:
    result = await s.execute(
        delete(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id)
    )
    return result.rowcount > 0


async def get_user_by_api_token_hash(s: AsyncSession, token_hash: str) -> User | None:
    user = await s.scalar(
        select(User).join(ApiToken, ApiToken.user_id == User.id).where(
            ApiToken.token_hash == token_hash
        )
    )
    if user is not None:
        await s.execute(
            update(ApiToken)
            .where(ApiToken.token_hash == token_hash)
            .values(last_used_at=func.now())
        )
    return user
