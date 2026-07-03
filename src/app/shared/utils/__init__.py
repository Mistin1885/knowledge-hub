import hashlib
import re
import secrets
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[^\w一-鿿-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or secrets.token_hex(4)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token(prefix: str = "") -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def stable_color(seed: str) -> str:
    """Deterministic color for presence cursors."""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:6], 16)
    hue = h % 360
    return f"hsl({hue}, 70%, 45%)"
