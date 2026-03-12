from __future__ import annotations

from pathlib import Path


def ensure_avatar_dirs(base_dir: Path, avatar_id: int) -> Path:
    avatar_dir = base_dir / str(avatar_id)
    (avatar_dir / "photos").mkdir(parents=True, exist_ok=True)
    return avatar_dir
