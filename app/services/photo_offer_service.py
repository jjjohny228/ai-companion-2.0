from __future__ import annotations

import random
from pathlib import Path

from app.db.models import Avatar, PhotoSendHistory, User
from app.services.premium_photo_service import PremiumPhotoService
from app.services.avatar_service import AvatarService


class PhotoOfferService:
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}

    @staticmethod
    def _collect_photos(photos_dir: Path) -> list[Path]:
        if not photos_dir.exists():
            return []
        return [path for path in photos_dir.iterdir() if path.suffix.lower() in PhotoOfferService.allowed_suffixes]

    @staticmethod
    def list_available_photos(assets_dir: Path, user: User, avatar: Avatar, bucket: str = "photos") -> list[Path]:
        avatar_dir = AvatarService.avatar_dir(assets_dir, avatar.id)
        photos_dir = avatar_dir / bucket
        all_photos = PhotoOfferService._collect_photos(photos_dir)
        sent_paths = {
            item.photo_path
            for item in PhotoSendHistory.select(PhotoSendHistory.photo_path).where(
                (PhotoSendHistory.user == user) & (PhotoSendHistory.avatar == avatar)
            )
        }
        return [path for path in all_photos if str(path) not in sent_paths]

    @staticmethod
    def has_available_photo(assets_dir: Path, user: User, avatar: Avatar) -> bool:
        return bool(PremiumPhotoService.available_for_user(avatar, user))

    @staticmethod
    def has_sent_lite_photo(assets_dir: Path, user: User, avatar: Avatar) -> bool:
        avatar_dir = AvatarService.avatar_dir(assets_dir, avatar.id)
        lite_dir = avatar_dir / "photos"
        lite_paths = {str(path) for path in PhotoOfferService._collect_photos(lite_dir)}
        if not lite_paths:
            return False
        return (
            PhotoSendHistory.select()
            .where(
                (PhotoSendHistory.user == user)
                & (PhotoSendHistory.avatar == avatar)
                & (PhotoSendHistory.photo_path.in_(lite_paths))
            )
            .exists()
        )

    @staticmethod
    def pick_random_lite_photo(assets_dir: Path, user: User, avatar: Avatar) -> Path | None:
        available = PhotoOfferService.list_available_photos(assets_dir, user, avatar, bucket="photos")
        if not available:
            return None
        photo = random.choice(available)
        PhotoSendHistory.create(user=user, avatar=avatar, photo_path=str(photo))
        return photo

    @staticmethod
    def pick_random_premium_photo(user: User, avatar: Avatar):
        available = PremiumPhotoService.available_for_user(avatar, user)
        if not available:
            return None
        photo = random.choice(available)
        PhotoSendHistory.create(user=user, avatar=avatar, photo_path=photo.photo_path)
        return photo
