"""StreamFetch CLI: Terminal Video & Stream Downloader"""

import sys
import os
import argparse
import json

# Ensure console UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.engine.extractor import media_extractor
from app.engine.downloader import media_downloader


def main():
    parser = argparse.ArgumentParser(
        description="StreamFetch — Universal Video & Stream Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py "https://www.youtube.com/watch?v=..."
  python cli.py "https://twitter.com/.../status/..." --format 720p
  python cli.py "https://tiktok.com/@.../video/..." --audio
  python cli.py "https://vimeo.com/..." --info
        """
    )

    parser.add_argument("url", help="Media URL to download or inspect")
    parser.add_argument("-f", "--format", default="best", help="Target resolution (best, 1080p, 720p, 480p)")
    parser.add_argument("-a", "--audio", action="store_true", help="Extract audio only as MP3")
    parser.add_argument("-i", "--info", action="store_true", help="Inspect and display metadata only")
    parser.add_argument("-c", "--cookies", help="Path to Netscape cookies.txt file for members-only / authenticated streams")

    args = parser.parse_args()

    if args.cookies:
        from app.core.config import settings
        settings.COOKIE_FILE = os.path.abspath(args.cookies)

    print("\n⚡ StreamFetch Universal Downloader")
    print("=" * 60)

    try:
        # If user only requested info
        if args.info:
            print(f"[🔍] Inspecting stream from: {args.url}...")
            info = media_extractor.inspect_url(args.url)
            print(f"\nTitle: {info['title']}")
            print(f"Platform: {info['platform']}")
            print(f"Uploader: {info['uploader']}")
            print(f"Duration: {info['duration_formatted']}")
            print("\nAvailable Quality Options:")
            for fmt in info.get("formats", []):
                print(f"  - {fmt['resolution']} ({fmt['ext']})")
            return

        # Perform download
        mode = "Audio (MP3)" if args.audio else f"Video ({args.format})"
        print(f"[⬇️] Downloading: {args.url}")
        print(f"[⚙️] Format Mode: {mode}")

        result = media_downloader.download(
            url=args.url,
            format_type=args.format,
            audio_only=args.audio
        )

        print("\n" + "=" * 60)
        print("✅ Download Completed Successfully!")
        print("=" * 60)
        print(f"Title: {result['title']}")
        print(f"File Saved: {result['file_path']}")
        print(f"File Size: {result['file_size_mb']} MB")
        print(f"Duration: {result['elapsed_time_seconds']}s")

    except ValueError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Download canceled by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
