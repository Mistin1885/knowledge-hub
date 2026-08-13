import re
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KM_", extra="ignore")

    database_url: str = "postgresql+asyncpg://km@localhost:5433/km"

    # Auth / sessions
    session_cookie_name: str = "km_session"
    session_ttl_days: int = 14
    cookie_secure: bool = False
    registration_open: bool = True
    # New non-admin users receive viewer access when this workspace exists.
    default_readonly_workspace_slug: str | None = "demo"

    # Storage
    uploads_dir: Path = Path("data/uploads")
    # KM_MAX_UPLOAD accepts human-readable binary units (for example 5G).
    # KM_MAX_UPLOAD_MB remains supported for existing deployments.
    max_upload: str | None = None
    max_upload_mb: int = 5 * 1024
    frontend_dist: Path = Path("src/frontend/dist")

    # Embeddings (any OpenAI-compatible endpoint); semantic search is disabled when unset
    embeddings_base_url: str | None = None
    embeddings_api_key: str | None = None
    embeddings_model: str = "text-embedding-3-small"
    embeddings_batch_size: int = 32
    embeddings_timeout_s: float = 30.0

    # Collaboration
    editor_mode: Literal["collaborative", "standard"] = "collaborative"
    collab_snapshot_debounce_s: float = 3.0
    collab_persist_every_updates: int = 50

    # File transfer features. Preview is separate from download so existing
    # inline page images can remain visible in a read-mostly deployment.
    file_uploads_enabled: bool = True
    file_downloads_enabled: bool = True
    file_previews_enabled: bool = True

    log_level: str = "INFO"

    @property
    def max_upload_bytes(self) -> int:
        if self.max_upload:
            match = re.fullmatch(r"\s*(\d+)\s*([KMGT]?)B?\s*", self.max_upload.upper())
            if not match:
                raise ValueError("KM_MAX_UPLOAD must look like 512M or 5G")
            value = int(match.group(1))
            power = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4}[match.group(2)]
            return value * (1024**power)
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
