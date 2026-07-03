"""Client for any OpenAI-compatible /embeddings endpoint. Disabled when unconfigured."""

import httpx

from app.shared.config.settings import settings
from app.shared.logging import get_logger

log = get_logger(__name__)


def enabled() -> bool:
    return bool(settings.embeddings_base_url)


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Returns one vector per input, or None if embeddings are disabled/unreachable."""
    if not enabled() or not texts:
        return None
    headers = {}
    if settings.embeddings_api_key:
        headers["Authorization"] = f"Bearer {settings.embeddings_api_key}"
    url = settings.embeddings_base_url.rstrip("/") + "/embeddings"
    vectors: list[list[float]] = []
    try:
        async with httpx.AsyncClient(timeout=settings.embeddings_timeout_s) as client:
            for i in range(0, len(texts), settings.embeddings_batch_size):
                batch = texts[i : i + settings.embeddings_batch_size]
                resp = await client.post(
                    url, headers=headers, json={"model": settings.embeddings_model, "input": batch}
                )
                resp.raise_for_status()
                data = sorted(resp.json()["data"], key=lambda d: d["index"])
                vectors.extend(d["embedding"] for d in data)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Embeddings request failed (%s); continuing without vectors", exc)
        return None
    return vectors
