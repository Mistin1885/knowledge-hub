from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KM_", extra="ignore")

    database_url: str = "postgresql+asyncpg://km@localhost:5433/km"

    # Auth / sessions
    session_cookie_name: str = "km_session"
    session_ttl_days: int = 14
    cookie_secure: bool = False
    registration_open: bool = True

    # Storage
    uploads_dir: Path = Path("data/uploads")
    max_upload_mb: int = 50
    frontend_dist: Path = Path("frontend/dist")

    # Embeddings (any OpenAI-compatible endpoint); semantic search is disabled when unset
    embeddings_base_url: str | None = None
    embeddings_api_key: str | None = None
    embeddings_model: str = "text-embedding-3-small"
    embeddings_batch_size: int = 32
    embeddings_timeout_s: float = 30.0

    # Collaboration
    collab_snapshot_debounce_s: float = 3.0
    collab_persist_every_updates: int = 50

    log_level: str = "INFO"


settings = Settings()
