from __future__ import annotations

from datetime import datetime

from aiogram.types import User as TgUser
from peewee import fn

from app.constants import DEFAULT_LANGUAGE
from app.db.models import User, UserProfile


class UserService:
    @staticmethod
    def get_or_create_from_telegram(tg_user: TgUser, admin_ids: tuple[int, ...]) -> tuple[User, UserProfile]:
        user, created = User.get_or_create(
            telegram_id=tg_user.id,
            defaults={
                "username": tg_user.username,
                "first_name": tg_user.first_name,
                "language_code": tg_user.language_code or DEFAULT_LANGUAGE,
                "is_admin": tg_user.id in admin_ids,
            },
        )
        if not created:
            user.username = tg_user.username
            user.first_name = tg_user.first_name
            user.language_code = tg_user.language_code or user.language_code or DEFAULT_LANGUAGE
            user.is_admin = tg_user.id in admin_ids
            user.last_seen_at = datetime.utcnow()
            user.save()
        profile, _ = UserProfile.get_or_create(
            user=user,
            defaults={"language": tg_user.language_code or DEFAULT_LANGUAGE},
        )
        return user, profile

    @staticmethod
    def set_language(profile: UserProfile, language: str) -> None:
        profile.language = language
        profile.updated_at = datetime.utcnow()
        profile.save()

    @staticmethod
    def get_or_create_by_telegram_id(telegram_id: int) -> tuple[User, UserProfile]:
        user, _ = User.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "language_code": DEFAULT_LANGUAGE,
                "is_admin": False,
            },
        )
        profile, _ = UserProfile.get_or_create(user=user, defaults={"language": DEFAULT_LANGUAGE})
        return user, profile

    @staticmethod
    def get_by_username(username: str) -> tuple[User, UserProfile] | None:
        normalized = username.strip().lstrip("@")
        if not normalized:
            return None
        user = User.get_or_none(fn.LOWER(User.username) == normalized.lower())
        if not user:
            return None
        profile, _ = UserProfile.get_or_create(user=user, defaults={"language": DEFAULT_LANGUAGE})
        return user, profile
