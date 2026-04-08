from __future__ import annotations

from app.db.base import database
from app.db.models import MODELS


def _get_table_columns(table_name: str) -> set[str]:
    cursor = database.execute_sql(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _migrate_user_profile_table() -> None:
    columns = _get_table_columns("userprofile")
    if "channel_bonus_granted" not in columns:
        database.execute_sql(
            "ALTER TABLE userprofile "
            "ADD COLUMN channel_bonus_granted INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_avatar_table() -> None:
    columns = _get_table_columns("avatar")
    if "display_name_ru" not in columns:
        database.execute_sql("ALTER TABLE avatar ADD COLUMN display_name_ru VARCHAR(255)")
    if "display_name_uk" not in columns:
        database.execute_sql("ALTER TABLE avatar ADD COLUMN display_name_uk VARCHAR(255)")
    if "description_ru" not in columns:
        database.execute_sql("ALTER TABLE avatar ADD COLUMN description_ru TEXT")
    if "description_uk" not in columns:
        database.execute_sql("ALTER TABLE avatar ADD COLUMN description_uk TEXT")


def create_tables() -> None:
    with database:
        database.create_tables(MODELS, safe=True)
        _migrate_user_profile_table()
        _migrate_avatar_table()
