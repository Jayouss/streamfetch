"""StreamFetch API v1 Endpoints"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.engine.extractor import media_extractor
from app.engine.downloader import media_downloader

router = APIRouter(tags=["Media Operations"])


# --- Schemas ---
class InspectRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})


class DownloadRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    format_type: str = Field(default="best", json_schema_extra={"example": "best"})  # "best", "1080p", "720p", "480p", "360p"
    audio_only: bool = Field(default=False)


# --- Endpoints ---

@router.post("/api/v1/info")
async def inspect_media_info(payload: InspectRequest):
    """Inspect URL and retrieve available formats, duration, thumbnail, and metadata."""
    try:
        info = media_extractor.inspect_url(payload.url)
        return info
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/download")
async def download_media(payload: DownloadRequest):
    """Execute media download to the server and return file metadata."""
    try:
        result = media_downloader.download(
            url=payload.url,
            format_type=payload.format_type,
            audio_only=payload.audio_only
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v1/files/{filename}")
async def serve_downloaded_file(filename: str):
    """Stream downloaded file directly to client browser."""
    safe_path = os.path.abspath(os.path.join(settings.DOWNLOAD_DIR, filename))

    # Path traversal protection
    if not safe_path.startswith(settings.DOWNLOAD_DIR):
        raise HTTPException(status_code=403, detail="Access denied.")

    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path=safe_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "download_dir": settings.DOWNLOAD_DIR
    }
