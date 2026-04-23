from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
import os


class Settings(BaseModel):
    db_path: Path = Field(default_factory=lambda: Path(os.getenv("APP_DB_PATH", "/home/fate/.openclaw/workspace/projects/telegram-ytm-queue/data/app.db")))
    allowed_chat_ids: set[int] = Field(default_factory=lambda: {
        int(x.strip()) for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if x.strip()
    })
    browser_mode: str = Field(default_factory=lambda: os.getenv("YTMUSIC_BROWSER_MODE", "mock"))
    ytmusic_headers_path: str | None = Field(default_factory=lambda: os.getenv("YTMUSIC_HEADERS_PATH"))
    dedupe_window_seconds: int = Field(default_factory=lambda: int(os.getenv("DEDUP_WINDOW_SECONDS", "120")))


def get_settings() -> Settings:
    settings = Settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
