"""Media Metadata Extractor powered by yt-dlp"""

from typing import Dict, Any, List, Optional
import os
import yt_dlp
from app.core.config import settings


class MediaExtractor:
    def __init__(self):
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        # Automatically attach cookies if available
        if os.path.exists(settings.COOKIE_FILE):
            self.ydl_opts["cookiefile"] = settings.COOKIE_FILE

    def inspect_url(self, url: str) -> Dict[str, Any]:
        """Extract media metadata and stream options without downloading."""
        if not url or not url.strip():
            raise ValueError("URL cannot be empty.")

        url = url.strip()
        opts = dict(self.ydl_opts)
        
        # Fresh check for cookies.txt
        if os.path.exists(settings.COOKIE_FILE):
            opts["cookiefile"] = settings.COOKIE_FILE

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info is None:
                    raise ValueError(f"Could not extract metadata from URL: {url}")

                # Format duration
                duration_sec = info.get("duration", 0) or 0
                mins, secs = divmod(int(duration_sec), 60)
                hours, mins = divmod(mins, 60)
                duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"

                # Parse formats
                raw_formats = info.get("formats", [])
                available_qualities = set()
                formats_summary: List[Dict[str, Any]] = []

                for f in raw_formats:
                    height = f.get("height")
                    ext = f.get("ext", "mp4")
                    vcodec = f.get("vcodec", "none")
                    acodec = f.get("acodec", "none")

                    if height and height not in available_qualities and vcodec != "none":
                        available_qualities.add(height)
                        formats_summary.append({
                            "format_id": f.get("format_id"),
                            "resolution": f"{height}p",
                            "ext": ext,
                            "filesize_approx": f.get("filesize") or f.get("filesize_approx")
                        })

                # Sort qualities descending
                formats_summary.sort(
                    key=lambda x: int(x["resolution"].replace("p", "")) if x["resolution"].replace("p", "").isdigit() else 0,
                    reverse=True
                )

                return {
                    "id": info.get("id"),
                    "title": info.get("title", "Untitled Video"),
                    "url": url,
                    "uploader": info.get("uploader") or info.get("channel", "Unknown"),
                    "duration_seconds": duration_sec,
                    "duration_formatted": duration_str,
                    "thumbnail": info.get("thumbnail"),
                    "platform": info.get("extractor_key", "Generic"),
                    "webpage_url": info.get("webpage_url", url),
                    "formats": formats_summary[:8]
                }
        except yt_dlp.utils.DownloadError as e:
            raise ValueError(f"Failed to access media stream: {str(e)}")
        except Exception as e:
            raise ValueError(f"Metadata extraction error: {str(e)}")


media_extractor = MediaExtractor()
