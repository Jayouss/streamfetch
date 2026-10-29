"""StreamFetch Configuration"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "StreamFetch Universal Downloader"
    VERSION: str = "0.1.0"

    PORT: int = 8000
    HOST: str = "0.0.0.0"

    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DOWNLOAD_DIR: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "downloads")
    COOKIE_FILE: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "cookies.txt")
    MAX_FILE_SIZE_MB: int = 500

    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
