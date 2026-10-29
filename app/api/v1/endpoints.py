"""StreamFetch API v1 Endpoints"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.engine.extractor import media_extractor
from app.engine.downloader import media_downloader
from app.engine.telegram_relay import telegram_relay

router = APIRouter(tags=["Media Operations"])


# --- Schemas ---
class InspectRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})


class DownloadRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    format_type: str = Field(default="best", json_schema_extra={"example": "best"})  # "best", "1080p", "720p", "480p", "360p"
    audio_only: bool = Field(default=False)


class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str


class TelegramSendRequest(BaseModel):
    url: str
    format_type: str = Field(default="720p")


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


@router.get("/api/v1/cookies/status")
async def get_cookie_status():
    """Check if YouTube / Platform membership cookies are active."""
    exists = os.path.exists(settings.COOKIE_FILE)
    size = os.path.getsize(settings.COOKIE_FILE) if exists else 0
    return {
        "active": exists and size > 0,
        "file_size_bytes": size,
        "message": "Authenticated session active (Members-Only & Private videos unlocked)" if (exists and size > 0) else "No session cookies detected (Public videos only)"
    }


@router.post("/api/v1/cookies/upload")
async def upload_cookie_file(file: UploadFile = File(...)):
    """Upload Netscape-format cookies.txt to authenticate members-only content."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    with open(settings.COOKIE_FILE, "wb") as f:
        f.write(content)

    return {
        "status": "SAVED",
        "message": f"Successfully activated session cookies ({len(content)} bytes). Members-only videos are now unlocked!"
    }


@router.delete("/api/v1/cookies/delete")
async def delete_cookie_file():
    """Remove stored session cookies."""
    if os.path.exists(settings.COOKIE_FILE):
        os.remove(settings.COOKIE_FILE)
    return {"message": "Session cookies removed."}


@router.get("/api/v1/telegram/status")
async def get_telegram_status():
    """Get Telegram Bot connection and configuration status."""
    return telegram_relay.get_status()


@router.post("/api/v1/telegram/config")
async def save_telegram_config(payload: TelegramConfigRequest):
    """Save and validate Telegram Bot Token and Chat ID."""
    try:
        res = telegram_relay.update_config(payload.bot_token, payload.chat_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/telegram/send")
async def send_media_to_telegram(payload: TelegramSendRequest):
    """Download video (using cookies/resolvers) and stream it directly to user's Telegram."""
    try:
        # Pre-check Telegram configuration before heavy download
        tg_status = telegram_relay.get_status()
        if not tg_status["configured"]:
            raise ValueError("Telegram Bot belum disetup. Klik tombol '✈️ Telegram' di kanan atas untuk memasukkan Bot Token & Chat ID.")

        # 1. Download video locally
        dl_res = media_downloader.download(
            url=payload.url,
            format_type=payload.format_type,
            audio_only=False
        )

        file_path = dl_res["file_path"]
        title = dl_res["title"]
        duration = dl_res.get("duration_seconds", 0)

        # 2. Upload to Telegram with streaming flag
        tg_res = telegram_relay.send_video(
            file_path=file_path,
            title=title,
            duration_seconds=duration
        )
        return tg_res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "download_dir": settings.DOWNLOAD_DIR
    }
