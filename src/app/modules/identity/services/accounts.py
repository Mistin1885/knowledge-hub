from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import User
from app.modules.identity.domain import tokens as token_policy
from app.modules.identity.infra import repo
from app.shared.config.settings import settings
from app.shared.exceptions import PermissionDeniedError, UnauthenticatedError, ValidationFailedError
from app.shared.utils import new_token, sha256_hex

_hasher = PasswordHash.recommended()


async def register(s: AsyncSession, email: str, name: str, password: str) -> User:
    if len(password) < 8:
        raise ValidationFailedError("Password must be at least 8 characters")
    if await repo.get_user_by_email(s, email):
        raise ValidationFailedError("Email already registered")
    first_user = await repo.count_users(s) == 0
    if not first_user and not settings.registration_open:
        raise PermissionDeniedError("Registration is closed; ask an admin to invite you")
    return await repo.create_user(
        s, email=email, name=name, password_hash=_hasher.hash(password), is_admin=first_user
    )


async def login(
    s: AsyncSession, email: str, password: str, user_agent: str | None
) -> tuple[User, str]:
    """Returns (user, raw session token). The raw token goes in the cookie; only its hash is stored."""
    user = await repo.get_user_by_email(s, email)
    if user is None or not _hasher.verify(password, user.password_hash):
        raise UnauthenticatedError("Invalid email or password")
    raw = new_token()
    await repo.create_session(
        s,
        user_id=user.id,
        token_hash=sha256_hex(raw),
        expires_at=token_policy.session_expiry(settings.session_ttl_days),
        user_agent=user_agent,
    )
    return user, raw


async def logout(s: AsyncSession, raw_token: str) -> None:
    await repo.delete_session(s, sha256_hex(raw_token))


async def authenticate_session(s: AsyncSession, raw_token: str) -> User | None:
    found = await repo.get_session_with_user(s, sha256_hex(raw_token))
    if found is None:
        return None
    sess, user = found
    if token_policy.is_expired(sess.expires_at):
        await repo.delete_session(s, sess.token_hash)
        return None
    return user


async def authenticate_api_token(s: AsyncSession, raw_token: str) -> User | None:
    if not raw_token.startswith(token_policy.API_TOKEN_PREFIX):
        return None
    return await repo.get_user_by_api_token_hash(s, sha256_hex(raw_token))
