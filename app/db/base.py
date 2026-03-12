from __future__ import annotations

from pathlib import Path

from peewee import SqliteDatabase


database = SqliteDatabase(None)


def init_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database.init(
        str(db_path),
        pragmas={
            "journal_mode": "wal",
            "cache_size": -1024 * 64,
            "foreign_keys": 1,
        },
    )
