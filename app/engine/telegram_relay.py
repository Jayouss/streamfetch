"""Telegram Relay Engine for streaming media directly to Telegram devices."""

import os
import math
import glob
import subprocess
from typing import Dict, Any, Optional, List
import requests
from app.core.config import settings


class TelegramRelay:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    def get_status(self) -> Dict[str, Any]:
        """Check connection status and bot username."""
        token = self.bot_token if self.bot_token is not None else settings.TELEGRAM_BOT_TOKEN
        chat = self.chat_id if self.chat_id is not None else settings.TELEGRAM_CHAT_ID

        has_token = bool(token)
        has_chat = bool(chat)
        bot_name = None

        if has_token:
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
                if r.status_code == 200 and r.json().get("ok"):
                    bot_name = r.json().get("result", {}).get("username")
            except Exception:
                pass

        return {
            "configured": bool(has_token and has_chat),
            "bot_username": bot_name,
            "has_token": has_token,
            "has_chat_id": has_chat,
            "chat_id": chat
        }

    def update_config(self, bot_token: str, chat_id: str) -> Dict[str, Any]:
        """Validate and store Telegram credentials."""
        bot_token = bot_token.strip()
        chat_id = chat_id.strip()

        if not bot_token or not chat_id:
            raise ValueError("Bot Token dan Chat ID wajib diisi.")

        try:
            r = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=8)
            if r.status_code != 200 or not r.json().get("ok"):
                raise ValueError("Token Telegram Bot tidak valid. Pastikan token benar dari @BotFather.")
            bot_info = r.json().get("result", {})
        except requests.RequestException as e:
            raise ValueError(f"Gagal menghubungi server Telegram: {str(e)}")

        self.bot_token = bot_token
        self.chat_id = chat_id
        settings.TELEGRAM_BOT_TOKEN = bot_token
        settings.TELEGRAM_CHAT_ID = chat_id

        # Persist to .env
        env_path = os.path.abspath(".env")
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = [line for line in f.readlines() if not line.startswith("TELEGRAM_BOT_TOKEN=") and not line.startswith("TELEGRAM_CHAT_ID=")]
        lines.append(f"TELEGRAM_BOT_TOKEN={bot_token}\n")
        lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return {
            "status": "CONFIGURED",
            "bot_username": bot_info.get("username"),
            "bot_first_name": bot_info.get("first_name"),
            "chat_id": chat_id,
            "message": f"Terkoneksi ke bot @{bot_info.get('username')}. Video siap dikirim ke Telegram!"
        }

    def split_video_for_telegram(self, file_path: str, target_max_mb: float = 42.0) -> List[str]:
        """Automatically split video into streamable parts under Telegram's 50MB limit using fast stream copy."""
        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb <= 48.0:
            return [file_path]

        # Extract duration via ffprobe
        duration = 0.0
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", file_path
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
            duration = float(out)
        except Exception:
            pass

        if duration <= 0:
            duration = 600.0

        num_parts = math.ceil(file_size_mb / target_max_mb)
        segment_time = max(10, int(duration / num_parts))

        base_dir = os.path.dirname(file_path)
        name, ext = os.path.splitext(os.path.basename(file_path))
        pattern = os.path.join(base_dir, f"{name}_part_%03d{ext}")

        split_cmd = [
            "ffmpeg", "-y", "-i", file_path,
            "-c", "copy",
            "-map", "0",
            "-segment_time", str(segment_time),
            "-f", "segment",
            "-reset_timestamps", "1",
            pattern
        ]
        try:
            subprocess.run(split_cmd, capture_output=True, check=True)
            search_pattern = os.path.join(base_dir, f"{name}_part_*{ext}")
            parts = sorted(glob.glob(search_pattern))
            if parts:
                return parts
        except Exception:
            pass

        return [file_path]

    def send_video(
        self,
        file_path: str,
        title: str,
        duration_seconds: int = 0,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send video file to Telegram with streamable flag enabled, automatically splitting if > 48MB."""
        token = self.bot_token if self.bot_token is not None else settings.TELEGRAM_BOT_TOKEN
        chat = self.chat_id if self.chat_id is not None else settings.TELEGRAM_CHAT_ID

        if not token or not chat:
            raise ValueError("Telegram Bot belum disetup. Klik tombol '✈️ Telegram' di kanan atas untuk memasukkan Bot Token & Chat ID.")

        if not os.path.exists(file_path):
            raise ValueError(f"File video tidak ditemukan di: {file_path}")

        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

        # Automatically segment large videos into streamable parts under Telegram 50MB limit
        parts = self.split_video_for_telegram(file_path, target_max_mb=42.0)
        total_parts = len(parts)

        url = f"https://api.telegram.org/bot{token}/sendVideo"
        last_message_id = None

        try:
            for idx, part_path in enumerate(parts, 1):
                part_mb = round(os.path.getsize(part_path) / (1024 * 1024), 2)
                if total_parts > 1:
                    part_caption = f"🎬 {title}\n📦 Bagian {idx}/{total_parts} ({part_mb} MB) • ⚡ Streamable on Phone"
                else:
                    part_caption = caption or f"🎬 {title}\n⚡ Streamable on Telegram Mobile"

                if len(part_caption) > 1024:
                    part_caption = part_caption[:1020] + "..."

                with open(part_path, "rb") as video_file:
                    files = {
                        "video": (os.path.basename(part_path), video_file, "video/mp4")
                    }
                    data = {
                        "chat_id": chat,
                        "caption": part_caption,
                        "supports_streaming": "true",
                    }
                    resp = requests.post(url, data=data, files=files, timeout=300)

                if resp.status_code != 200 or not resp.json().get("ok"):
                    err_desc = resp.json().get("description", "Unknown Telegram API error")
                    if "chat not found" in err_desc.lower():
                        err_desc += ". Pastikan kamu sudah klik START (/start) pada bot Telegram milikmu terlebih dahulu!"
                    raise ValueError(f"Telegram API Error: {err_desc}")

                last_message_id = resp.json().get("result", {}).get("message_id")

                # Clean up temporary split part
                if part_path != file_path and os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass

            if total_parts > 1:
                success_msg = f"Video berukuran {file_size_mb} MB berhasil dipecah otomatis menjadi {total_parts} bagian (kualitas utuh) dan SEMUANYA telah terkirim ke Telegram! Buka Telegram di HP untuk langsung streaming."
            else:
                success_msg = f"Berhasil dikirim ke Telegram! ({file_size_mb} MB). Kamu bisa langsung buka Telegram di HP dan putar videonya."

            return {
                "status": "SENT",
                "message_id": last_message_id,
                "file_size_mb": file_size_mb,
                "parts_sent": total_parts,
                "title": title,
                "message": success_msg
            }
        except requests.RequestException as e:
            raise ValueError(f"Gagal mengunggah ke Telegram: {str(e)}")


telegram_relay = TelegramRelay()
