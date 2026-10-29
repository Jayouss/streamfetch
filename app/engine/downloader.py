"""Universal Media Download Pipeline powered by yt-dlp"""

import os
import time
from typing import Dict, Any, Optional
import yt_dlp

from app.core.config import settings


class MediaDownloader:
    def __init__(self, download_dir: str = settings.DOWNLOAD_DIR):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

    def download(
        self,
        url: str,
        format_type: str = "best",
        audio_only: bool = False
    ) -> Dict[str, Any]:
        """Download stream from URL to the target download directory."""
        if not url or not url.strip():
            raise ValueError("URL cannot be empty.")

        start_time = time.time()
        output_template = os.path.join(self.download_dir, "%(title).80s-%(id)s.%(ext)s")

        ydl_opts: Dict[str, Any] = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        # Automatically use authenticated session cookies if present
        if os.path.exists(settings.COOKIE_FILE):
            ydl_opts["cookiefile"] = settings.COOKIE_FILE

        if audio_only:
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
        elif format_type == "best":
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            # Custom quality like '1080p', '720p', etc.
            res = format_type.replace("p", "")
            if res.isdigit():
                ydl_opts["format"] = f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[height<={res}][ext=mp4]/best"
            else:
                ydl_opts["format"] = "best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)

                # If audio postprocessing was applied, extension is .mp3
                if audio_only:
                    base, _ = os.path.splitext(downloaded_file)
                    downloaded_file = f"{base}.mp3"

                file_size = os.path.getsize(downloaded_file) if os.path.exists(downloaded_file) else 0

                return {
                    "status": "COMPLETED",
                    "title": info.get("title", "Downloaded Media"),
                    "file_path": downloaded_file,
                    "file_name": os.path.basename(downloaded_file),
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size / (1024 * 1024), 2),
                    "duration_seconds": info.get("duration", 0),
                    "elapsed_time_seconds": round(time.time() - start_time, 2),
                    "platform": info.get("extractor_key", "Generic")
                }
        except yt_dlp.utils.DownloadError as e:
            raise ValueError(f"Download failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected download error: {str(e)}")


media_downloader = MediaDownloader()
