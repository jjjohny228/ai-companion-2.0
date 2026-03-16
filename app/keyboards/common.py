from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.constants import LANGUAGES
from app.db.models import Avatar, Channel, Gift


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


def avatar_keyboard(avatar: Avatar, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Choose", callback_data=f"avatar:choose:{avatar.id}")
    if has_prev:
        builder.button(text="⬅️", callback_data=f"avatar:nav:{avatar.id}:prev")
    if has_next:
        builder.button(text="➡️", callback_data=f"avatar:nav:{avatar.id}:next")
    builder.adjust(1, 2)
    return builder.as_markup()


def main_menu_keyboard(
    chat_text: str,
    avatar_text: str,
    language_text: str,
    subscription_text: str,
    gift_text: str,
    premium_text: str,
) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=chat_text), KeyboardButton(text=avatar_text))
    builder.row(KeyboardButton(text=language_text), KeyboardButton(text=subscription_text))
    builder.row(KeyboardButton(text=gift_text), KeyboardButton(text=premium_text))
    return builder.as_markup(resize_keyboard=True)


def subscription_plans_keyboard(plan_rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan_code, title in plan_rows:
        builder.button(text=title, callback_data=f"plan:{plan_code}")
    builder.adjust(1)
    return builder.as_markup()


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Day", callback_data="admin_stats:day")
    builder.button(text="Month", callback_data="admin_stats:month")
    builder.button(text="All time", callback_data="admin_stats:all")
    builder.adjust(1)
    return builder.as_markup()


def admin_avatar_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Add avatar"), KeyboardButton(text="Edit avatars"))
    builder.row(KeyboardButton(text="Back to admin"))
    return builder.as_markup(resize_keyboard=True)


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Statistics"), KeyboardButton(text="Avatars"))
    builder.row(KeyboardButton(text="Gifts"), KeyboardButton(text="Add channel"))
    builder.row(KeyboardButton(text="Broadcast"), KeyboardButton(text="Send user"))
    builder.row(KeyboardButton(text="Download DB"))
    return builder.as_markup(resize_keyboard=True)


def gifts_keyboard(gifts: list[Gift]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gift in gifts:
        builder.button(text=f"{gift.title} - {gift.stars_price} Stars", callback_data=f"gift:{gift.id}")
    builder.adjust(1)
    return builder.as_markup()


def premium_photos_keyboard(avatar_id: int, prev_photo_id: int | None, next_photo_id: int | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if prev_photo_id:
        builder.button(text="⬅️", callback_data=f"premium_gallery:{avatar_id}:{prev_photo_id}")
    if next_photo_id:
        builder.button(text="➡️", callback_data=f"premium_gallery:{avatar_id}:{next_photo_id}")
    builder.adjust(2)
    return builder.as_markup()


def admin_gift_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Add gift"), KeyboardButton(text="Edit gifts"))
    builder.row(KeyboardButton(text="Back to admin"))
    return builder.as_markup(resize_keyboard=True)
