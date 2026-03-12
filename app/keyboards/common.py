from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.constants import LANGUAGES
from app.db.models import Avatar, Channel


def subscription_keyboard(channels: list[Channel], check_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        if channel.username_or_invite_link:
            builder.button(text=channel.title, url=channel.username_or_invite_link)
    builder.button(text=check_text, callback_data="subscription:check")
    builder.adjust(1)
    return builder.as_markup()


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, title in LANGUAGES.items():
        builder.button(text=title, callback_data=f"language:{code}")
    builder.adjust(1)
    return builder.as_markup()


def avatar_keyboard(avatars: list[Avatar]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for avatar in avatars:
        builder.button(text=avatar.display_name, callback_data=f"avatar:{avatar.id}")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_keyboard(chat_text: str, avatar_text: str, language_text: str, subscription_text: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=chat_text), KeyboardButton(text=avatar_text))
    builder.row(KeyboardButton(text=language_text), KeyboardButton(text=subscription_text))
    return builder.as_markup(resize_keyboard=True)


def subscription_plans_keyboard(plan_rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan_code, title in plan_rows:
        builder.button(text=title, callback_data=f"plan:{plan_code}")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Stats day"), KeyboardButton(text="Stats month"))
    builder.row(KeyboardButton(text="Stats all"), KeyboardButton(text="Add avatar"))
    builder.row(KeyboardButton(text="Add channel"), KeyboardButton(text="Download DB"))
    return builder.as_markup(resize_keyboard=True)
