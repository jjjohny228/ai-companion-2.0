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


def avatar_keyboard(avatar: Avatar, has_prev: bool, has_next: bool, choose_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=choose_text, callback_data=f"avatar:choose:{avatar.id}")
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


def admin_stats_keyboard(day_text: str, month_text: str, all_time_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=day_text, callback_data="admin_stats:day")
    builder.button(text=month_text, callback_data="admin_stats:month")
    builder.button(text=all_time_text, callback_data="admin_stats:all")
    builder.adjust(1)
    return builder.as_markup()


def admin_avatar_keyboard(add_avatar_text: str, edit_avatars_text: str, back_text: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=add_avatar_text), KeyboardButton(text=edit_avatars_text))
    builder.row(KeyboardButton(text=back_text))
    return builder.as_markup(resize_keyboard=True)


def admin_channel_keyboard(add_channel_text: str, edit_channels_text: str, back_text: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=add_channel_text), KeyboardButton(text=edit_channels_text))
    builder.row(KeyboardButton(text=back_text))
    return builder.as_markup(resize_keyboard=True)


def admin_cancel_keyboard(cancel_text: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=cancel_text))
    return builder.as_markup(resize_keyboard=True)


def admin_menu_keyboard(
    statistics_text: str,
    avatars_text: str,
    gifts_text: str,
    add_channel_text: str,
    broadcast_text: str,
    send_user_text: str,
    grant_balance_text: str,
    download_db_text: str,
) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=statistics_text), KeyboardButton(text=avatars_text))
    builder.row(KeyboardButton(text=gifts_text), KeyboardButton(text=add_channel_text))
    builder.row(KeyboardButton(text=broadcast_text), KeyboardButton(text=send_user_text))
    builder.row(KeyboardButton(text=grant_balance_text), KeyboardButton(text=download_db_text))
    return builder.as_markup(resize_keyboard=True)


def gifts_keyboard(gift_rows: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gift_id, title in gift_rows:
        builder.button(text=title, callback_data=f"gift:{gift_id}")
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


def admin_gift_keyboard(add_gift_text: str, edit_gifts_text: str, back_text: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=add_gift_text), KeyboardButton(text=edit_gifts_text))
    builder.row(KeyboardButton(text=back_text))
    return builder.as_markup(resize_keyboard=True)
