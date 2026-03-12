from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(slots=True)
class Settings:
    bot_token: str
    openai_api_key: str
    openai_model: str
    admin_ids: tuple[int, ...]
    db_path: Path
    assets_dir: Path
    default_free_avatar_messages: int
    summary_window_size: int
    summary_batch_size: int
    log_level: str


def _parse_admin_ids(raw_value: str | None) -> tuple[int, ...]:
    if not raw_value:
        return tuple()
    return tuple(int(chunk.strip()) for chunk in raw_value.split(",") if chunk.strip())


def load_settings() -> Settings:
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        db_path=Path(os.getenv("DB_PATH", BASE_DIR / "data" / "bot.sqlite3")),
        assets_dir=Path(os.getenv("ASSETS_DIR", BASE_DIR / "assets" / "avatars")),
        default_free_avatar_messages=int(os.getenv("DEFAULT_FREE_AVATAR_MESSAGES", "10")),
        summary_window_size=int(os.getenv("SUMMARY_WINDOW_SIZE", "10")),
        summary_batch_size=int(os.getenv("SUMMARY_BATCH_SIZE", "10")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
