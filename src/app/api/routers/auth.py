import uuid

from fastapi import APIRouter, Request, Response, status

from app.api.deps import DB, CurrentUser
from app.api.schemas.auth import LoginIn, RegisterIn, TokenCreatedOut, TokenCreateIn, TokenOut
from app.api.schemas.common import UserOut
from app.modules.identity.services import accounts, api_tokens
from app.shared.config.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, s: DB):
    return await accounts.register(s, body.email, body.name, body.password)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response, s: DB):
    user, token = await accounts.login(
        s, body.email, body.password, request.headers.get("user-agent")
    )
    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, s: DB):
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await accounts.logout(s, token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.get("/tokens", response_model=list[TokenOut])
async def list_tokens(user: CurrentUser, s: DB):
    return await api_tokens.list_for_user(s, user.id)


@router.post("/tokens", response_model=TokenCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_token(body: TokenCreateIn, user: CurrentUser, s: DB):
    row, raw = await api_tokens.create(s, user.id, body.name)
    return TokenCreatedOut(id=row.id, name=row.name, token=raw)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(token_id: uuid.UUID, user: CurrentUser, s: DB):
    await api_tokens.revoke(s, user.id, token_id)
