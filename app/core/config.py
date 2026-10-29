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

    DOWNLOAD_DIR: str = os.path.abspath("./downloads")
    COOKIE_FILE: str = os.path.abspath("./cookies.txt")
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
