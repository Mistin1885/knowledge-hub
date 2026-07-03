"""Pure token/session policy — no I/O."""

from datetime import UTC, datetime, timedelta

API_TOKEN_PREFIX = "kmt_"
SESSION_TOKEN_BYTES = 32


def session_expiry(ttl_days: int) -> datetime:
    return datetime.now(UTC) + timedelta(days=ttl_days)


def is_expired(expires_at: datetime) -> bool:
    return expires_at <= datetime.now(UTC)


def token_display_prefix(token: str) -> str:
    return token[:12]
