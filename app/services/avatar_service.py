from __future__ import annotations

from pathlib import Path

from app.db.models import Avatar, UserProfile


class AvatarService:
    @staticmethod
    def list_active() -> list[Avatar]:
        return list(Avatar.select().where(Avatar.is_active == True).order_by(Avatar.sort_order, Avatar.id))

    @staticmethod
    def get_active(avatar_id: int) -> Avatar | None:
        return Avatar.get_or_none((Avatar.id == avatar_id) & (Avatar.is_active == True))

    @staticmethod
    def select_avatar(profile: UserProfile, avatar: Avatar) -> None:
        profile.selected_avatar = avatar
        profile.save()

    @staticmethod
    def avatar_dir(assets_dir: Path, avatar_id: int) -> Path:
        return assets_dir / str(avatar_id)
