"""Universal Media Download Pipeline powered by yt-dlp and Custom Resolvers."""

import os
import time
from typing import Dict, Any, Optional
import yt_dlp

from app.core.config import settings
from app.engine.custom_resolvers import resolve_custom_stream, resolve_generic_html5


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

        url = url.strip()
        start_time = time.time()
        output_template = os.path.join(self.download_dir, "%(title).80s-%(id)s.%(ext)s")

        ydl_opts: Dict[str, Any] = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        # Check for custom resolver (e.g. jwplyr, vidoy)
        custom_data = resolve_custom_stream(url)
        target_url = url
        custom_platform = "Generic"

        if custom_data:
            target_url = custom_data["stream_url"]
            custom_platform = custom_data.get("platform", "Custom")
            if "headers" in custom_data:
                ydl_opts["http_headers"] = custom_data["headers"]

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
        elif format_type == "best" or custom_data:
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
                info = ydl.extract_info(target_url, download=True)
                downloaded_file = ydl.prepare_filename(info)

                # If audio postprocessing was applied, extension is .mp3
                if audio_only:
                    base, _ = os.path.splitext(downloaded_file)
                    downloaded_file = f"{base}.mp3"

                file_size = os.path.getsize(downloaded_file) if os.path.exists(downloaded_file) else 0

                title = custom_data.get("title") if (custom_data and custom_data.get("title")) else info.get("title", "Downloaded Media")

                return {
                    "status": "COMPLETED",
                    "title": title,
                    "file_path": downloaded_file,
                    "file_name": os.path.basename(downloaded_file),
                    "file_size_bytes": file_size,
                    "file_size_mb": round(file_size / (1024 * 1024), 2),
                    "duration_seconds": info.get("duration", 0),
                    "elapsed_time_seconds": round(time.time() - start_time, 2),
                    "platform": custom_platform if custom_data else info.get("extractor_key", "Generic")
                }
        except yt_dlp.utils.DownloadError as e:
            raise ValueError(f"Download failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected download error: {str(e)}")


media_downloader = MediaDownloader()
