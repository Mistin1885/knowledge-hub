from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.engine import session_factory
from app.infra.db.models import User
from app.modules.identity.services import accounts
from app.shared.config.settings import settings
from app.shared.exceptions import UnauthenticatedError


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


DB = Annotated[AsyncSession, Depends(get_db)]


async def _resolve_user(
    s: AsyncSession, cookie_token: str | None, auth_header: str | None
) -> User | None:
    if auth_header and auth_header.lower().startswith("bearer "):
        return await accounts.authenticate_api_token(s, auth_header[7:].strip())
    if cookie_token:
        return await accounts.authenticate_session(s, cookie_token)
    return None


async def current_user(request: Request, s: DB) -> User:
    user = await _resolve_user(
        s,
        request.cookies.get(settings.session_cookie_name),
        request.headers.get("authorization"),
    )
    if user is None:
        raise UnauthenticatedError("Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def websocket_user(ws: WebSocket, s: AsyncSession) -> User | None:
    """Resolve the user on a WebSocket handshake (cookie or bearer)."""
    return await _resolve_user(
        s, ws.cookies.get(settings.session_cookie_name), ws.headers.get("authorization")
    )
