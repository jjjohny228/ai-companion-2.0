from __future__ import annotations

from app.db.base import database
from app.db.models import MODELS


def create_tables() -> None:
    with database:
        database.create_tables(MODELS)
