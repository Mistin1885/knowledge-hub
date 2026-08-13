from app.shared.config.settings import settings
from app.shared.exceptions import PermissionDeniedError


def require_file_uploads() -> None:
    if not settings.file_uploads_enabled:
        raise PermissionDeniedError("File uploads and imports are disabled for this deployment")


def require_file_downloads() -> None:
    if not settings.file_downloads_enabled:
        raise PermissionDeniedError("File downloads and exports are disabled for this deployment")


def require_file_previews() -> None:
    if not settings.file_previews_enabled:
        raise PermissionDeniedError("File previews are disabled for this deployment")
