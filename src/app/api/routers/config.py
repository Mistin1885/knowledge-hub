from fastapi import APIRouter
from pydantic import BaseModel

from app.shared.config.settings import settings

router = APIRouter(tags=["config"])


class RuntimeConfigOut(BaseModel):
    editor_mode: str
    file_uploads_enabled: bool
    file_downloads_enabled: bool
    file_previews_enabled: bool


@router.get("/config", response_model=RuntimeConfigOut)
async def runtime_config():
    return RuntimeConfigOut(
        editor_mode=settings.editor_mode,
        file_uploads_enabled=settings.file_uploads_enabled,
        file_downloads_enabled=settings.file_downloads_enabled,
        file_previews_enabled=settings.file_previews_enabled,
    )
