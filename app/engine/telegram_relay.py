"""Telegram Relay Engine for streaming media directly to Telegram devices."""

import os
from typing import Dict, Any, Optional
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

    def send_video(
        self,
        file_path: str,
        title: str,
        duration_seconds: int = 0,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send video file to Telegram with streamable flag enabled."""
        token = self.bot_token if self.bot_token is not None else settings.TELEGRAM_BOT_TOKEN
        chat = self.chat_id if self.chat_id is not None else settings.TELEGRAM_CHAT_ID

        if not token or not chat:
            raise ValueError("Telegram Bot belum disetup. Klik tombol '✈️ Telegram' di kanan atas untuk memasukkan Bot Token & Chat ID.")

        if not os.path.exists(file_path):
            raise ValueError(f"File video tidak ditemukan di: {file_path}")

        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

        # Standard Bot API limit is 50MB
        if file_size_mb > 50:
            raise ValueError(
                f"Ukuran video ({file_size_mb} MB) melebihi batas upload Telegram Bot API standar (50 MB). "
                f"Saran: Di opsi kualitas, pilih 720p atau 480p agar ukuran video di bawah 50 MB."
            )

        video_caption = caption or f"🎬 {title}\n⚡ Streamable on Telegram Mobile"
        if len(video_caption) > 1024:
            video_caption = video_caption[:1020] + "..."

        url = f"https://api.telegram.org/bot{token}/sendVideo"

        try:
            with open(file_path, "rb") as video_file:
                files = {
                    "video": (os.path.basename(file_path), video_file, "video/mp4")
                }
                data = {
                    "chat_id": chat,
                    "caption": video_caption,
                    "supports_streaming": "true",
                }
                if duration_seconds > 0:
                    data["duration"] = int(duration_seconds)

                resp = requests.post(url, data=data, files=files, timeout=180)

            if resp.status_code != 200 or not resp.json().get("ok"):
                err_desc = resp.json().get("description", "Unknown Telegram API error")
                if "chat not found" in err_desc.lower():
                    err_desc += ". Pastikan kamu sudah klik START (/start) pada bot Telegram milikmu terlebih dahulu!"
                raise ValueError(f"Telegram API Error: {err_desc}")

            res_data = resp.json().get("result", {})
            return {
                "status": "SENT",
                "message_id": res_data.get("message_id"),
                "file_size_mb": file_size_mb,
                "title": title,
                "message": f"Berhasil dikirim ke Telegram! ({file_size_mb} MB). Kamu bisa langsung buka Telegram di HP dan putar videonya."
            }
        except requests.RequestException as e:
            raise ValueError(f"Gagal mengunggah ke Telegram: {str(e)}")


telegram_relay = TelegramRelay()
