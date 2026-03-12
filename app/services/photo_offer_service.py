from __future__ import annotations

import random
from pathlib import Path

from app.db.models import Avatar, PhotoSendHistory, User
from app.services.avatar_service import AvatarService


class PhotoOfferService:
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}

    @staticmethod
    def list_available_photos(assets_dir: Path, user: User, avatar: Avatar) -> list[Path]:
        avatar_dir = AvatarService.avatar_dir(assets_dir, avatar.id)
        photos_dir = avatar_dir / "photos"
        if not photos_dir.exists():
            return []
        all_photos = [path for path in photos_dir.iterdir() if path.suffix.lower() in PhotoOfferService.allowed_suffixes]
        sent_paths = {
            item.photo_path
            for item in PhotoSendHistory.select(PhotoSendHistory.photo_path).where(
                (PhotoSendHistory.user == user) & (PhotoSendHistory.avatar == avatar)
            )
        }
        return [path for path in all_photos if str(path) not in sent_paths]

    @staticmethod
    def has_available_photo(assets_dir: Path, user: User, avatar: Avatar) -> bool:
        return bool(PhotoOfferService.list_available_photos(assets_dir, user, avatar))

    @staticmethod
    def pick_random_photo(assets_dir: Path, user: User, avatar: Avatar) -> Path | None:
        available = PhotoOfferService.list_available_photos(assets_dir, user, avatar)
        if not available:
            return None
        photo = random.choice(available)
        PhotoSendHistory.create(user=user, avatar=avatar, photo_path=str(photo))
        return photo
