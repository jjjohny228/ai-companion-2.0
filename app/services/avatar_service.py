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

    @staticmethod
    def list_active_ids() -> list[int]:
        return [avatar.id for avatar in AvatarService.list_active()]

    @staticmethod
    def get_active_by_offset(current_avatar_id: int | None, offset: int) -> Avatar | None:
        avatars = AvatarService.list_active()
        if not avatars:
            return None
        ids = [avatar.id for avatar in avatars]
        if current_avatar_id not in ids:
            return avatars[0]
        current_index = ids.index(current_avatar_id)
        next_index = (current_index + offset) % len(ids)
        return avatars[next_index]

    @staticmethod
    def get_navigation_flags(current_avatar_id: int) -> tuple[bool, bool]:
        avatars = AvatarService.list_active()
        if len(avatars) <= 1:
            return False, False
        ids = [avatar.id for avatar in avatars]
        if current_avatar_id not in ids:
            return False, False
        return True, True
