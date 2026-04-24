from __future__ import annotations

import logging
import shutil
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message
from aiogram.types.input_paid_media_photo import InputPaidMediaPhoto
from aiogram.types.input_paid_media_video import InputPaidMediaVideo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from peewee import IntegrityError

from app.config import Settings
from app.db.models import Avatar, Channel, Gift, User
from app.keyboards.common import admin_avatar_keyboard, admin_cancel_keyboard, admin_channel_keyboard, admin_gift_keyboard, admin_menu_keyboard, admin_stats_keyboard
from app.services.custom_request_service import CustomRequestService
from app.services.stats_service import StatsService
from app.services.translation_service import TranslationService
from app.services.user_service import UserService
from app.states.admin import (
    AdminAvatarCreateState,
    AdminAvatarEditState,
    AdminAvatarUploadState,
    AdminBroadcastState,
    AdminChannelCreateState,
    AdminChannelEditState,
    AdminDirectSendState,
    AdminGrantBalanceState,
    AdminGiftCreateState,
    AdminGiftEditState,
    AdminPremiumPhotoState,
)
from app.texts import tr
from app.utils.files import ensure_avatar_dirs
from app.services.premium_photo_service import PremiumPhotoService


def build_router(settings: Settings) -> Router:
    router = Router()
    logger = logging.getLogger(__name__)
    translation_service = TranslationService(settings)
    admin_back_texts = {"Back to admin", "Назад в админку", "Назад в адмінку"}
    admin_cancel_texts = {"Cancel", "Отмена", "Скасувати"}
    admin_statistics_texts = {"Statistics", "Статистика"}
    admin_avatars_texts = {"Avatars", "Аватары", "Аватари"}
    admin_channels_texts = {"Channels", "Каналы", "Канали"}
    admin_gifts_texts = {"Gifts", "Подарки", "Подарунки"}
    admin_add_channel_texts = {"Add channel", "Добавить канал", "Додати канал"}
    admin_broadcast_texts = {"Broadcast", "Рассылка", "Розсилка"}
    admin_send_user_texts = {"Send user", "Отправить пользователю", "Надiслати користувачу"}
    admin_grant_balance_texts = {"Grant balance", "Выдать баланс", "Видати баланс"}
    admin_download_db_texts = {"Download DB", "Скачать БД", "Завантажити БД"}
    admin_add_avatar_texts = {"Add avatar", "Добавить аватара", "Додати аватара"}
    admin_edit_avatars_texts = {"Edit avatars", "Редактировать аватаров", "Редагувати аватарiв"}
    admin_edit_channels_texts = {"Edit channels", "Редактировать каналы", "Редагувати канали"}
    admin_add_gift_texts = {"Add gift", "Добавить подарок", "Додати подарунок"}
    admin_edit_gifts_texts = {"Edit gifts", "Редактировать подарки", "Редагувати подарунки"}

    def is_admin(user_id: int) -> bool:
        return user_id in settings.admin_ids

    def admin_menu_markup(language: str):
        return admin_menu_keyboard(
            tr(language, "admin_statistics"),
            tr(language, "admin_avatars"),
            tr(language, "admin_gifts"),
            tr(language, "admin_channels"),
            tr(language, "admin_broadcast"),
            tr(language, "admin_send_user"),
            tr(language, "admin_grant_balance"),
            tr(language, "admin_download_db"),
        )

    def admin_language_by_user_id(user_id: int) -> str:
        user = User.get_or_none(User.telegram_id == user_id)
        if not user:
            return "en"
        _, profile = UserService.get_or_create_by_telegram_id(user.telegram_id)
        return profile.language

    async def set_upload_target(state: FSMContext, avatar_id: int, media_bucket: str = "photos") -> None:
        await state.update_data(upload_avatar_id=avatar_id, upload_media_bucket=media_bucket)

    async def get_upload_target(state: FSMContext) -> tuple[int | None, str]:
        data = await state.get_data()
        avatar_id = data.get("upload_avatar_id")
        media_bucket = data.get("upload_media_bucket", "photos")
        return (int(avatar_id) if avatar_id else None, media_bucket)

    def avatar_main_photo_path(avatar_id: int) -> Path:
        return ensure_avatar_dirs(settings.assets_dir, avatar_id) / "main.jpg"

    def gift_photo_path(gift_id: int) -> Path:
        gift_dir = settings.assets_dir.parent / "gifts" / str(gift_id)
        gift_dir.mkdir(parents=True, exist_ok=True)
        return gift_dir / "gift.jpg"

    def fill_avatar_translations(avatar: Avatar) -> None:
        avatar.description_ru = translation_service.translate_text(avatar.description, "ru")
        avatar.description_uk = translation_service.translate_text(avatar.description, "uk")
        avatar.save()

    def parse_bool_flag(raw_value: str) -> bool | None:
        normalized = raw_value.strip().lower()
        if normalized in {"1", "y", "yes", "true", "да"}:
            return True
        if normalized in {"0", "n", "no", "false", "нет"}:
            return False
        return None

    async def save_telegram_photo(message: Message, destination: Path) -> None:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await message.bot.download_file(file.file_path, destination=destination)

    def avatars_list_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for avatar in Avatar.select().order_by(Avatar.sort_order, Avatar.id):
            status = "ON" if avatar.is_active else "OFF"
            builder.button(text=f"{avatar.display_name} [{status}]", callback_data=f"admin_avatar:open:{avatar.id}")
        builder.adjust(1)
        return builder.as_markup()

    def channels_list_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for channel in Channel.select().order_by(Channel.id.desc()):
            status = "ON" if channel.is_active else "OFF"
            builder.button(text=f"{channel.title} [{status}]", callback_data=f"admin_channel:open:{channel.id}")
        builder.adjust(1)
        return builder.as_markup()

    def gifts_list_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for gift in Gift.select().order_by(Gift.stars_price, Gift.id):
            status = "ON" if gift.is_active else "OFF"
            builder.button(text=f"{gift.title} [{status}]", callback_data=f"admin_gift:open:{gift.id}")
        builder.adjust(1)
        return builder.as_markup()

    def avatar_edit_keyboard(avatar_id: int, language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=tr(language, "admin_inline_main_photo"), callback_data=f"admin_avatar:edit:{avatar_id}:main_photo")
        builder.button(text=tr(language, "admin_inline_name"), callback_data=f"admin_avatar:edit:{avatar_id}:display_name")
        builder.button(text=tr(language, "admin_inline_description"), callback_data=f"admin_avatar:edit:{avatar_id}:description")
        builder.button(text=tr(language, "admin_inline_system_prompt"), callback_data=f"admin_avatar:edit:{avatar_id}:system_prompt")
        builder.button(text=tr(language, "admin_inline_upload_lite"), callback_data=f"admin_avatar:bucket:{avatar_id}:photos")
        builder.button(text=tr(language, "admin_inline_upload_premium"), callback_data=f"admin_avatar:bucket:{avatar_id}:premium")
        builder.button(text=tr(language, "admin_inline_toggle_active"), callback_data=f"admin_avatar:toggle:{avatar_id}")
        builder.button(text=tr(language, "admin_inline_delete"), callback_data=f"admin_avatar:delete:{avatar_id}")
        builder.adjust(1)
        return builder.as_markup()

    def channel_edit_keyboard(channel_id: int, language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=tr(language, "admin_inline_title"), callback_data=f"admin_channel:edit:{channel_id}:title")
        builder.button(text=tr(language, "admin_inline_link"), callback_data=f"admin_channel:edit:{channel_id}:username_or_invite_link")
        builder.button(text=tr(language, "admin_inline_toggle_active"), callback_data=f"admin_channel:toggle:{channel_id}")
        builder.button(text=tr(language, "admin_inline_delete"), callback_data=f"admin_channel:delete:{channel_id}")
        builder.adjust(1)
        return builder.as_markup()

    def skip_main_photo_keyboard(language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=tr(language, "admin_inline_skip"), callback_data="admin_avatar:create:skip_main_photo")
        return builder.as_markup()

    def continue_media_keyboard(prefix: str, language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=tr(language, "admin_inline_skip"), callback_data=f"{prefix}:skip")
        builder.button(text=tr(language, "admin_inline_done"), callback_data=f"{prefix}:done")
        builder.adjust(2)
        return builder.as_markup()

    def skip_gift_photo_keyboard(language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=tr(language, "admin_inline_skip"), callback_data="admin_gift:create:skip_photo")
        return builder.as_markup()

    def gift_edit_keyboard(gift_id: int, language: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text=tr(language, "admin_inline_photo"), callback_data=f"admin_gift:edit:{gift_id}:photo")
        builder.button(text=tr(language, "admin_inline_title"), callback_data=f"admin_gift:edit:{gift_id}:title")
        builder.button(text=tr(language, "admin_inline_description"), callback_data=f"admin_gift:edit:{gift_id}:description")
        builder.button(text=tr(language, "admin_inline_price"), callback_data=f"admin_gift:edit:{gift_id}:price")
        builder.button(text=tr(language, "admin_inline_toggle_active"), callback_data=f"admin_gift:toggle:{gift_id}")
        builder.adjust(1)
        return builder.as_markup()

    def avatar_bucket_dir(avatar_id: int, bucket: str) -> Path:
        return ensure_avatar_dirs(settings.assets_dir, avatar_id) / bucket

    def optional_button_markup(raw_button: str | None):
        if not raw_button:
            return None
        parts = [item.strip() for item in raw_button.split("|", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None
        builder = InlineKeyboardBuilder()
        builder.button(text=parts[0], url=parts[1])
        return builder.as_markup()

    def log_blocked_user(chat_id: int, action: str, exc: TelegramForbiddenError) -> None:
        logger.warning("bot_blocked_by_user action=%s chat_id=%s error=%s", action, chat_id, exc)

    async def send_to_user(chat_id: int, text: str, media_kind: str | None, media_path: str | None, button: str | None, bot) -> bool:
        reply_markup = optional_button_markup(button)
        try:
            if media_kind == "photo" and media_path:
                await bot.send_photo(chat_id, FSInputFile(media_path), caption=text, reply_markup=reply_markup)
                return True
            if media_kind == "video" and media_path:
                await bot.send_video(chat_id, FSInputFile(media_path), caption=text, reply_markup=reply_markup)
                return True
            await bot.send_message(chat_id, text, reply_markup=reply_markup)
            return True
        except TelegramForbiddenError as exc:
            log_blocked_user(chat_id, "direct_or_broadcast_message", exc)
            return False

    async def send_file_id_media_to_user(
        chat_id: int,
        text: str,
        media_kind: str,
        media_file_id: str,
        button: str | None,
        bot,
    ) -> bool:
        reply_markup = optional_button_markup(button)
        try:
            if media_kind == "photo":
                await bot.send_photo(chat_id, media_file_id, caption=text, reply_markup=reply_markup)
                return True
            await bot.send_video(chat_id, media_file_id, caption=text, reply_markup=reply_markup)
            return True
        except TelegramForbiddenError as exc:
            log_blocked_user(chat_id, f"broadcast_{media_kind}", exc)
            return False

    async def send_paid_media_to_user(
        chat_id: int,
        text: str,
        media_kind: str,
        media_file_id: str,
        star_count: int,
        button: str | None,
        bot,
    ) -> bool:
        reply_markup = optional_button_markup(button)
        if media_kind == "photo":
            media = [InputPaidMediaPhoto(media=media_file_id)]
        else:
            media = [InputPaidMediaVideo(media=media_file_id)]
        try:
            await bot.send_paid_media(
                chat_id=chat_id,
                star_count=star_count,
                media=media,
                caption=text,
                reply_markup=reply_markup,
                protect_content=True,
            )
            return True
        except TelegramForbiddenError as exc:
            log_blocked_user(chat_id, f"paid_{media_kind}", exc)
            return False

    async def start_premium_photo_metadata_flow(state: FSMContext, avatar_id: int, saved_path: Path) -> None:
        await state.update_data(premium_avatar_id=avatar_id, pending_premium_photo_path=str(saved_path))
        await state.set_state(AdminPremiumPhotoState.waiting_price)

    @router.message(Command("admin"))
    async def admin_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(
            tr(profile.language, "admin_menu"),
            reply_markup=admin_menu_markup(profile.language),
        )

    @router.message(F.text.in_(admin_back_texts))
    async def back_to_admin(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(
            tr(profile.language, "admin_menu"),
            reply_markup=admin_menu_markup(profile.language),
        )

    @router.message(F.text.in_(admin_cancel_texts))
    async def cancel_admin_flow(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        current_state = await state.get_state()
        if current_state is None:
            return
        await state.clear()
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(tr(language, "admin_menu"), reply_markup=admin_menu_markup(language))

    @router.message(F.text.in_(admin_statistics_texts))
    async def statistics_menu(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(
            tr(profile.language, "admin_choose_period"),
            reply_markup=admin_stats_keyboard(
                tr(profile.language, "admin_stats_day"),
                tr(profile.language, "admin_stats_month"),
                tr(profile.language, "admin_stats_all"),
            ),
        )

    @router.callback_query(F.data.startswith("admin_stats:"))
    async def statistics_callback(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        period = callback.data.split(":", 1)[1]
        stats = StatsService.collect(period)
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            "\n".join(
                [
                    f"{tr(language, 'admin_period')}: {period}",
                    f"{tr(language, 'admin_users')}: {stats['users']}",
                    f"{tr(language, 'admin_messages')}: {stats['messages']}",
                    f"{tr(language, 'admin_payments')}: {stats['payments']}",
                    f"{tr(language, 'admin_stars')}: {stats['stars']}",
                    f"{tr(language, 'admin_top_avatar_messages')}: {stats['top_avatar_messages']}",
                ]
            )
        )
        await callback.answer()

    @router.message(F.text.in_(admin_avatars_texts))
    async def avatars_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(
            tr(profile.language, "admin_avatar_management"),
            reply_markup=admin_avatar_keyboard(
                tr(profile.language, "admin_add_avatar"),
                tr(profile.language, "admin_edit_avatars"),
                tr(profile.language, "admin_back"),
            ),
        )

    @router.message(F.text.in_(admin_gifts_texts))
    async def gifts_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(
            tr(profile.language, "admin_gift_management"),
            reply_markup=admin_gift_keyboard(
                tr(profile.language, "admin_add_gift"),
                tr(profile.language, "admin_edit_gifts"),
                tr(profile.language, "admin_back"),
            ),
        )

    @router.message(F.text.in_(admin_channels_texts))
    async def channels_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(
            tr(profile.language, "admin_channel_management"),
            reply_markup=admin_channel_keyboard(
                tr(profile.language, "admin_add_channel"),
                tr(profile.language, "admin_edit_channels"),
                tr(profile.language, "admin_back"),
            ),
        )

    @router.message(F.text.in_(admin_add_avatar_texts))
    async def start_add_avatar(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminAvatarCreateState.waiting_slug)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_avatar_slug"))

    @router.message(AdminAvatarCreateState.waiting_slug, F.text)
    async def create_avatar_slug(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        slug = message.text.strip()
        if Avatar.get_or_none(Avatar.slug == slug):
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_avatar_slug_taken"))
            return
        await state.update_data(slug=slug)
        await state.set_state(AdminAvatarCreateState.waiting_name)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_avatar_name"))

    @router.message(AdminAvatarCreateState.waiting_name, F.text)
    async def create_avatar_name(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(name=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_description)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_avatar_description"))

    @router.message(AdminAvatarCreateState.waiting_description, F.text)
    async def create_avatar_description(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(description=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_system_prompt)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_avatar_system_prompt"))

    @router.message(AdminAvatarCreateState.waiting_system_prompt, F.text)
    async def create_avatar_system_prompt(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(system_prompt=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_main_photo)
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_send_avatar_main_photo"),
            reply_markup=skip_main_photo_keyboard(admin_language_by_user_id(message.from_user.id)),
        )

    @router.callback_query(F.data == "admin_avatar:create:skip_main_photo")
    async def skip_main_photo(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        data = await state.get_data()
        try:
            avatar = Avatar.create(
                slug=data["slug"],
                display_name=data["name"],
                description=data["description"],
                system_prompt=data["system_prompt"],
            )
        except IntegrityError:
            await state.set_state(AdminAvatarCreateState.waiting_slug)
            await callback.message.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_avatar_slug_taken"))
            await callback.answer()
            return
        fill_avatar_translations(avatar)
        ensure_avatar_dirs(settings.assets_dir, avatar.id)
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarCreateState.waiting_lite_media)
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            f"{tr(language, 'admin_avatar_created').format(id=avatar.id)}\n"
            f"{tr(language, 'admin_send_lite_media')}",
            reply_markup=continue_media_keyboard("admin_avatar:create:lite", language),
        )
        await callback.answer()

    @router.message(AdminAvatarCreateState.waiting_main_photo, F.photo)
    async def create_avatar_main_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            avatar = Avatar.create(
                slug=data["slug"],
                display_name=data["name"],
                description=data["description"],
                system_prompt=data["system_prompt"],
            )
        except IntegrityError:
            await state.set_state(AdminAvatarCreateState.waiting_slug)
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_avatar_slug_taken"))
            return
        fill_avatar_translations(avatar)
        path = avatar_main_photo_path(avatar.id)
        await save_telegram_photo(message, path)
        avatar.main_photo_path = str(path)
        avatar.save()
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarCreateState.waiting_lite_media)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            f"{tr(language, 'admin_avatar_created').format(id=avatar.id)}\n"
            f"{tr(language, 'admin_main_photo_saved')}\n"
            f"{tr(language, 'admin_send_lite_media')}",
            reply_markup=continue_media_keyboard("admin_avatar:create:lite", language),
        )

    @router.callback_query(F.data == "admin_avatar:create:lite:skip")
    @router.callback_query(F.data == "admin_avatar:create:lite:done")
    async def finish_lite_media(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        data = await state.get_data()
        avatar_id = data.get("upload_avatar_id")
        if not avatar_id:
            await callback.answer()
            return
        await set_upload_target(state, int(avatar_id), "premium")
        await state.set_state(AdminAvatarCreateState.waiting_premium_media)
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            tr(language, "admin_send_premium_media"),
            reply_markup=continue_media_keyboard("admin_avatar:create:premium", language),
        )
        await callback.answer()

    @router.callback_query(F.data == "admin_avatar:create:premium:skip")
    @router.callback_query(F.data == "admin_avatar:create:premium:done")
    async def finish_premium_media(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        data = await state.get_data()
        avatar_id = data.get("upload_avatar_id")
        if not avatar_id:
            await callback.answer()
            return
        avatar = Avatar.get_or_none(Avatar.id == int(avatar_id))
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await set_upload_target(state, int(avatar_id), "photos")
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            tr(language, "admin_avatar_setup_finished").format(id=avatar.id if avatar else avatar_id)
        )
        await callback.answer()

    @router.message(F.text.in_(admin_edit_avatars_texts))
    async def edit_avatars(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_choose_avatar_to_edit"),
            reply_markup=avatars_list_keyboard(),
        )

    @router.message(F.text.in_(admin_add_gift_texts))
    async def start_add_gift(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminGiftCreateState.waiting_slug)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_gift_slug"))

    @router.message(AdminGiftCreateState.waiting_slug, F.text)
    async def create_gift_slug(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(gift_slug=message.text.strip())
        await state.set_state(AdminGiftCreateState.waiting_title)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_gift_title"))

    @router.message(AdminGiftCreateState.waiting_title, F.text)
    async def create_gift_title(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(gift_title=message.text.strip())
        await state.set_state(AdminGiftCreateState.waiting_description)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_gift_description"))

    @router.message(AdminGiftCreateState.waiting_description, F.text)
    async def create_gift_description(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(gift_description=message.text.strip())
        await state.set_state(AdminGiftCreateState.waiting_price)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_gift_price"))

    @router.message(AdminGiftCreateState.waiting_price, F.text)
    async def create_gift_price(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_price"))
            return
        await state.update_data(gift_price=int(message.text.strip()))
        await state.set_state(AdminGiftCreateState.waiting_photo)
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_send_gift_photo"),
            reply_markup=skip_gift_photo_keyboard(admin_language_by_user_id(message.from_user.id)),
        )

    @router.callback_query(F.data == "admin_gift:create:skip_photo")
    async def create_gift_skip_photo(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        data = await state.get_data()
        gift = Gift.create(
            slug=data["gift_slug"],
            title=data["gift_title"],
            description=data["gift_description"],
            stars_price=int(data["gift_price"]),
        )
        await state.clear()
        await callback.message.answer(
            tr(admin_language_by_user_id(callback.from_user.id), "admin_gift_created").format(id=gift.id)
        )
        await callback.answer()

    @router.message(AdminGiftCreateState.waiting_photo, F.photo)
    async def create_gift_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        gift = Gift.create(
            slug=data["gift_slug"],
            title=data["gift_title"],
            description=data["gift_description"],
            stars_price=int(data["gift_price"]),
        )
        path = gift_photo_path(gift.id)
        await save_telegram_photo(message, path)
        gift.photo_path = str(path)
        gift.save()
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_gift_created").format(id=gift.id))

    @router.message(F.text.in_(admin_edit_gifts_texts))
    async def edit_gifts(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_choose_gift_to_edit"),
            reply_markup=gifts_list_keyboard(),
        )

    @router.callback_query(F.data.startswith("admin_gift:open:"))
    async def open_gift_editor(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        gift_id = int(callback.data.split(":")[2])
        gift = Gift.get_or_none(Gift.id == gift_id)
        if not gift:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_gift_not_found"), show_alert=True)
            return
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            tr(language, "admin_gift_summary").format(
                id=gift.id,
                title=gift.title,
                price=gift.stars_price,
                description=gift.description,
                active=gift.is_active,
            ),
            reply_markup=gift_edit_keyboard(gift.id, language),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_gift:toggle:"))
    async def toggle_gift(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            return
        gift_id = int(callback.data.split(":")[2])
        gift = Gift.get_or_none(Gift.id == gift_id)
        if not gift:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_gift_not_found"), show_alert=True)
            return
        gift.is_active = not gift.is_active
        gift.save()
        await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_gift_active_toggled").format(active=gift.is_active))

    @router.callback_query(F.data.startswith("admin_gift:edit:"))
    async def select_gift_edit_field(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, gift_id, field_name = callback.data.split(":")
        gift = Gift.get_or_none(Gift.id == int(gift_id))
        if not gift:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_gift_not_found"), show_alert=True)
            return
        await state.set_state(AdminGiftEditState.waiting_value)
        await state.update_data(edit_gift_id=gift.id, edit_gift_field=field_name)
        if field_name == "photo":
            await callback.message.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_send_new_gift_photo"))
        else:
            await callback.message.answer(
                tr(admin_language_by_user_id(callback.from_user.id), "admin_send_new_value_for").format(field=field_name)
            )
        await callback.answer()

    @router.message(AdminGiftEditState.waiting_value, F.photo)
    async def update_gift_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if data.get("edit_gift_field") != "photo":
            return
        gift = Gift.get_or_none(Gift.id == int(data["edit_gift_id"]))
        if not gift:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_gift_not_found"))
            return
        path = gift_photo_path(gift.id)
        await save_telegram_photo(message, path)
        gift.photo_path = str(path)
        gift.save()
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_gift_photo_updated").format(id=gift.id))

    @router.message(AdminGiftEditState.waiting_value, F.text)
    async def update_gift_text_field(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        field_name = data.get("edit_gift_field")
        gift = Gift.get_or_none(Gift.id == int(data["edit_gift_id"]))
        if not gift or not message.text:
            return
        value = message.text.strip()
        if field_name == "price":
            if not value.isdigit():
                await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_price"))
                return
            gift.stars_price = int(value)
        elif field_name == "title":
            gift.title = value
        elif field_name == "description":
            gift.description = value
        else:
            return
        gift.save()
        await state.clear()
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_gift_field_updated").format(field=field_name, id=gift.id)
        )

    @router.callback_query(F.data.startswith("admin_avatar:open:"))
    async def open_avatar_editor(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        avatar_id = int(callback.data.split(":")[2])
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "avatar_not_found"), show_alert=True)
            return
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            tr(language, "admin_avatar_summary").format(
                id=avatar.id,
                name=avatar.display_name,
                description=avatar.description or "-",
                active=avatar.is_active,
            ),
            reply_markup=avatar_edit_keyboard(avatar.id, language),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_avatar:delete:"))
    async def delete_avatar(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        avatar_id = int(callback.data.split(":")[2])
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "avatar_not_found"), show_alert=True)
            return
        avatar_name = avatar.display_name
        avatar.delete_instance(recursive=True, delete_nullable=False)
        await callback.message.answer(
            tr(admin_language_by_user_id(callback.from_user.id), "admin_avatar_deleted").format(name=avatar_name)
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_avatar:toggle:"))
    async def toggle_avatar(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            return
        avatar_id = int(callback.data.split(":")[2])
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "avatar_not_found"), show_alert=True)
            return
        avatar.is_active = not avatar.is_active
        avatar.save()
        await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_avatar_active_toggled").format(active=avatar.is_active))

    @router.callback_query(F.data.startswith("admin_avatar:bucket:"))
    async def select_avatar_bucket(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, avatar_id, bucket = callback.data.split(":")
        avatar = Avatar.get_or_none(Avatar.id == int(avatar_id))
        if not avatar:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "avatar_not_found"), show_alert=True)
            return
        await set_upload_target(state, avatar.id, bucket)
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        label = "premium" if bucket == "premium" else "lite"
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            tr(language, "admin_upload_target_set").format(
                id=avatar.id,
                name=avatar.display_name,
                label=label,
                suffix=tr(language, "admin_upload_suffix_premium" if bucket == "premium" else "admin_upload_suffix_lite"),
            )
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_avatar:edit:"))
    async def select_edit_field(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, avatar_id, field_name = callback.data.split(":")
        avatar = Avatar.get_or_none(Avatar.id == int(avatar_id))
        if not avatar:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "avatar_not_found"), show_alert=True)
            return
        await state.set_state(AdminAvatarEditState.waiting_value)
        await state.update_data(edit_avatar_id=avatar.id, edit_field=field_name)
        if field_name == "main_photo":
            await callback.message.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_send_new_main_photo"))
        elif field_name == "display_name":
            await callback.message.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_send_new_display_name"))
        elif field_name == "description":
            await callback.message.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_send_new_description"))
        else:
            await callback.message.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_send_new_system_prompt"))
        await callback.answer()

    @router.message(AdminAvatarEditState.waiting_value, F.photo)
    async def update_avatar_main_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if data.get("edit_field") != "main_photo":
            return
        avatar = Avatar.get_or_none(Avatar.id == int(data["edit_avatar_id"]))
        if not avatar:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "avatar_not_found"))
            return
        path = avatar_main_photo_path(avatar.id)
        await save_telegram_photo(message, path)
        avatar.main_photo_path = str(path)
        avatar.save()
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_main_photo_updated").format(id=avatar.id))

    @router.message(AdminAvatarEditState.waiting_value, F.text)
    async def update_avatar_text_field(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        field_name = data.get("edit_field")
        if field_name not in {"display_name", "description", "system_prompt"} or not message.text:
            return
        avatar = Avatar.get_or_none(Avatar.id == int(data["edit_avatar_id"]))
        if not avatar:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "avatar_not_found"))
            return
        setattr(avatar, field_name, message.text.strip())
        if field_name == "description":
            avatar.description_ru = translation_service.translate_text(avatar.description, "ru")
            avatar.description_uk = translation_service.translate_text(avatar.description, "uk")
        avatar.save()
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await set_upload_target(state, avatar.id, "photos")
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_avatar_field_updated").format(field=field_name, id=avatar.id)
        )

    @router.message(Command("use_avatar"))
    async def use_avatar(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id) or not message.text:
            return
        payload = message.text.replace("/use_avatar", "", 1).strip()
        if not payload.isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_use_avatar_format"))
            return
        avatar = Avatar.get_or_none(Avatar.id == int(payload))
        if not avatar:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "avatar_not_found"))
            return
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_current_upload_target").format(
                id=avatar.id,
                name=avatar.display_name,
            )
        )

    @router.message(Command("clear_avatar_context"))
    async def clear_avatar_context(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_avatar_context_cleared"))

    @router.message(F.photo)
    async def upload_avatar_gallery_photo(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        current_state = await state.get_state()
        if current_state == AdminBroadcastState.waiting_media.state:
            data = await state.get_data()
            file_id = message.photo[-1].file_id
            users = list(User.select())
            sent = 0
            for user in users:
                try:
                    await message.bot.send_photo(
                        user.telegram_id,
                        file_id,
                        caption=data["broadcast_text"],
                        reply_markup=optional_button_markup(data.get("broadcast_button")),
                    )
                    sent += 1
                except Exception:
                    continue
            await state.clear()
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_broadcast_photo_sent").format(sent=sent))
            return
        if current_state == AdminDirectSendState.waiting_media.state:
            await state.update_data(direct_media_kind="photo", direct_media_file_id=message.photo[-1].file_id)
            await state.set_state(AdminDirectSendState.waiting_stars)
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_unlock_photo_price"))
            return
        if current_state == AdminAvatarCreateState.waiting_main_photo.state:
            return
        if current_state == AdminAvatarEditState.waiting_value.state:
            return
        if current_state == AdminGiftCreateState.waiting_photo.state:
            return
        if current_state == AdminGiftEditState.waiting_value.state:
            return
        if current_state == AdminPremiumPhotoState.waiting_price.state:
            return
        avatar_id, media_bucket = await get_upload_target(state)
        if not avatar_id:
            return
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "avatar_not_found"))
            return
        photo = message.photo[-1]
        avatar_dir = avatar_bucket_dir(avatar.id, media_bucket)
        destination = avatar_dir / f"{photo.file_unique_id}.jpg"
        await save_telegram_photo(message, destination)
        if media_bucket == "premium":
            await start_premium_photo_metadata_flow(state, avatar.id, destination)
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_premium_photo_uploaded"))
            return
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_lite_photo_saved").format(id=avatar.id))

    @router.message(F.document)
    async def upload_avatar_zip(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        current_state = await state.get_state()
        if current_state in {
            AdminGiftCreateState.waiting_photo.state,
            AdminGiftEditState.waiting_value.state,
            AdminPremiumPhotoState.waiting_price.state,
        }:
            return
        document = message.document
        if not document or not document.file_name or not document.file_name.lower().endswith(".zip"):
            return
        avatar_id, media_bucket = await get_upload_target(state)
        if not avatar_id:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_avatar_not_selected_upload"))
            return
        if media_bucket == "premium":
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_premium_upload_one_by_one"))
            return
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "avatar_not_found"))
            return
        avatar_dir = ensure_avatar_dirs(settings.assets_dir, avatar.id)
        zip_path = avatar_dir / document.file_name
        file = await message.bot.get_file(document.file_id)
        await message.bot.download_file(file.file_path, destination=zip_path)
        shutil.unpack_archive(str(zip_path), str(avatar_bucket_dir(avatar.id, media_bucket)))
        zip_path.unlink(missing_ok=True)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_zip_extracted").format(id=avatar.id))

    @router.message(AdminPremiumPhotoState.waiting_price, F.text)
    async def premium_photo_price(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_stars_price"))
            return
        await state.update_data(pending_premium_price=int(message.text.strip()))
        data = await state.get_data()
        avatar = Avatar.get_or_none(Avatar.id == int(data["premium_avatar_id"]))
        if not avatar:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "avatar_not_found"))
            return
        PremiumPhotoService.create(
            avatar=avatar,
            photo_path=data["pending_premium_photo_path"],
            stars_price=int(data["pending_premium_price"]),
            description="",
        )
        upload_avatar_id = data.get("upload_avatar_id")
        upload_media_bucket = data.get("upload_media_bucket", "premium")
        await state.clear()
        if upload_avatar_id:
            await set_upload_target(state, int(upload_avatar_id), upload_media_bucket)
            await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_premium_photo_saved"))

    @router.message(F.text.in_(admin_add_channel_texts))
    async def add_channel_start(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminChannelCreateState.waiting_chat_id)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_channel_chat_id"))

    @router.message(F.text.in_(admin_edit_channels_texts))
    async def edit_channels(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_choose_channel_to_edit"),
            reply_markup=channels_list_keyboard(),
        )

    @router.callback_query(F.data.startswith("admin_channel:open:"))
    async def open_channel_editor(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        channel_id = int(callback.data.split(":")[2])
        channel = Channel.get_or_none(Channel.id == channel_id)
        if not channel:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_channel_not_found"), show_alert=True)
            return
        language = admin_language_by_user_id(callback.from_user.id)
        await callback.message.answer(
            tr(language, "admin_channel_summary").format(
                id=channel.id,
                title=channel.title,
                chat_id=channel.telegram_channel_id,
                link=channel.username_or_invite_link or "-",
                is_private=channel.is_private,
                join_request=channel.requires_join_request,
                active=channel.is_active,
            ),
            reply_markup=channel_edit_keyboard(channel.id, language),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_channel:toggle:"))
    async def toggle_channel(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            return
        channel_id = int(callback.data.split(":")[2])
        channel = Channel.get_or_none(Channel.id == channel_id)
        if not channel:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_channel_not_found"), show_alert=True)
            return
        channel.is_active = not channel.is_active
        channel.save()
        await callback.answer(
            tr(admin_language_by_user_id(callback.from_user.id), "admin_channel_active_toggled").format(active=channel.is_active)
        )

    @router.callback_query(F.data.startswith("admin_channel:delete:"))
    async def delete_channel(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        channel_id = int(callback.data.split(":")[2])
        channel = Channel.get_or_none(Channel.id == channel_id)
        if not channel:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_channel_not_found"), show_alert=True)
            return
        title = channel.title
        channel.delete_instance()
        await callback.message.answer(
            tr(admin_language_by_user_id(callback.from_user.id), "admin_channel_deleted").format(title=title)
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_channel:edit:"))
    async def select_channel_edit_field(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, channel_id, field_name = callback.data.split(":")
        channel = Channel.get_or_none(Channel.id == int(channel_id))
        if not channel:
            await callback.answer(tr(admin_language_by_user_id(callback.from_user.id), "admin_channel_not_found"), show_alert=True)
            return
        await state.set_state(AdminChannelEditState.waiting_value)
        await state.update_data(edit_channel_id=channel.id, edit_channel_field=field_name)
        language = admin_language_by_user_id(callback.from_user.id)
        if field_name == "title":
            await callback.message.answer(tr(language, "admin_send_new_channel_title"))
        else:
            await callback.message.answer(tr(language, "admin_send_new_channel_link"))
        await callback.answer()

    @router.message(AdminChannelEditState.waiting_value, F.text)
    async def update_channel_text_field(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        field_name = data.get("edit_channel_field")
        channel = Channel.get_or_none(Channel.id == int(data["edit_channel_id"]))
        if not channel or not message.text:
            return
        value = message.text.strip()
        if field_name == "username_or_invite_link" and value.lower() == "skip":
            value = None
        setattr(channel, field_name, value)
        channel.save()
        await state.clear()
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_channel_field_updated").format(
                field=field_name,
                id=channel.id,
            )
        )

    @router.message(Command("add_channel"))
    async def add_channel_command(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminChannelCreateState.waiting_chat_id)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_channel_chat_id"))

    @router.message(AdminChannelCreateState.waiting_chat_id, F.text)
    async def add_channel_chat_id(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        value = message.text.strip()
        if not value.lstrip("-").isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_chat_id"))
            return
        await state.update_data(channel_chat_id=int(value))
        await state.set_state(AdminChannelCreateState.waiting_title)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_channel_title"))

    @router.message(AdminChannelCreateState.waiting_title, F.text)
    async def add_channel_title(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(channel_title=message.text.strip())
        await state.set_state(AdminChannelCreateState.waiting_link)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_channel_link"))

    @router.message(AdminChannelCreateState.waiting_link, F.text)
    async def add_channel_link(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        link = message.text.strip()
        await state.update_data(channel_link=None if link.lower() == "skip" else link)
        await state.set_state(AdminChannelCreateState.waiting_is_private)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_is_channel_private"))

    @router.message(AdminChannelCreateState.waiting_is_private, F.text)
    async def add_channel_is_private(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        is_private = parse_bool_flag(message.text)
        if is_private is None:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_yes_no_10"))
            return
        await state.update_data(channel_is_private=is_private)
        await state.set_state(AdminChannelCreateState.waiting_join_request)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_requires_join_request"))

    @router.message(AdminChannelCreateState.waiting_join_request, F.text)
    async def add_channel_join_request(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        requires_join_request = parse_bool_flag(message.text)
        if requires_join_request is None:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_yes_no_10"))
            return
        data = await state.get_data()
        channel, created = Channel.get_or_create(
            telegram_channel_id=int(data["channel_chat_id"]),
            defaults={
                "title": data["channel_title"],
                "username_or_invite_link": data.get("channel_link"),
                "is_private": bool(data["channel_is_private"]),
                "requires_join_request": requires_join_request,
                "is_active": True,
            },
        )
        if not created:
            channel.title = data["channel_title"]
            channel.username_or_invite_link = data.get("channel_link")
            channel.is_private = bool(data["channel_is_private"])
            channel.requires_join_request = requires_join_request
            channel.is_active = True
            channel.save()
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_channel_saved").format(title=channel.title))

    @router.message(F.text.in_(admin_download_db_texts))
    async def download_db(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        db_file = Path(settings.db_path)
        if not db_file.exists():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_database_not_found"))
            return
        await message.answer_document(
            FSInputFile(db_file),
            caption=tr(admin_language_by_user_id(message.from_user.id), "admin_database_caption"),
        )

    @router.message(F.text.in_(admin_broadcast_texts))
    async def broadcast_start(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminBroadcastState.waiting_text)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_broadcast_text"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminBroadcastState.waiting_text, F.text)
    async def broadcast_text(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(broadcast_text=message.text.strip())
        await state.set_state(AdminBroadcastState.waiting_button)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_button_or_skip"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminBroadcastState.waiting_button, F.text)
    async def broadcast_button(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        button_text = None if message.text.strip().lower() == "skip" else message.text.strip()
        await state.update_data(broadcast_button=button_text)
        await state.set_state(AdminBroadcastState.waiting_media)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_broadcast_media_or_skip"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminBroadcastState.waiting_media, F.text)
    async def broadcast_without_media(message: Message, state: FSMContext) -> None:
        if not message.text or message.text.strip().lower() != "skip":
            return
        data = await state.get_data()
        users = list(User.select())
        sent = 0
        for user in users:
            try:
                if await send_to_user(user.telegram_id, data["broadcast_text"], None, None, data.get("broadcast_button"), message.bot):
                    sent += 1
            except Exception:
                logger.exception("broadcast_send_failed chat_id=%s media_kind=text", user.telegram_id)
                continue
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_broadcast_sent").format(sent=sent))

    @router.message(AdminBroadcastState.waiting_media, F.photo)
    async def broadcast_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        file_id = message.photo[-1].file_id
        users = list(User.select())
        sent = 0
        for user in users:
            try:
                if await send_file_id_media_to_user(
                    user.telegram_id,
                    data["broadcast_text"],
                    "photo",
                    file_id,
                    data.get("broadcast_button"),
                    message.bot,
                ):
                    sent += 1
            except Exception:
                logger.exception("broadcast_send_failed chat_id=%s media_kind=photo", user.telegram_id)
                continue
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_broadcast_photo_sent").format(sent=sent))

    @router.message(AdminBroadcastState.waiting_media, F.video)
    async def broadcast_video(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        file_id = message.video.file_id
        users = list(User.select())
        sent = 0
        for user in users:
            try:
                if await send_file_id_media_to_user(
                    user.telegram_id,
                    data["broadcast_text"],
                    "video",
                    file_id,
                    data.get("broadcast_button"),
                    message.bot,
                ):
                    sent += 1
            except Exception:
                logger.exception("broadcast_send_failed chat_id=%s media_kind=video", user.telegram_id)
                continue
        await state.clear()
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_broadcast_video_sent").format(sent=sent))

    @router.message(F.text.in_(admin_send_user_texts))
    async def direct_send_start(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminDirectSendState.waiting_user_id)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_target_user_id"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(F.text.in_(admin_grant_balance_texts))
    async def grant_balance_start(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminGrantBalanceState.waiting_username)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_target_username"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminGrantBalanceState.waiting_username, F.text)
    async def grant_balance_username(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        resolved = UserService.get_by_username(message.text.strip())
        if not resolved:
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_username_not_found"))
            return
        user, _ = resolved
        await state.update_data(grant_user_id=user.id, grant_username=user.username or message.text.strip().lstrip("@"))
        await state.set_state(AdminGrantBalanceState.waiting_amount)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_balance_amount"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminGrantBalanceState.waiting_amount, F.text)
    async def grant_balance_amount(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_amount"))
            return
        data = await state.get_data()
        user = User.get_or_none(User.id == int(data["grant_user_id"]))
        if not user:
            await state.clear()
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_user_not_found"))
            return
        _, profile = UserService.get_or_create_by_telegram_id(user.telegram_id)
        amount = int(message.text.strip())
        profile.paid_message_balance += amount
        profile.save()
        await state.clear()
        await message.answer(
            tr(admin_language_by_user_id(message.from_user.id), "admin_balance_added").format(
                amount=amount,
                username=data["grant_username"],
                balance=profile.paid_message_balance,
            )
        )

    @router.message(AdminDirectSendState.waiting_user_id, F.text)
    async def direct_send_user_id(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_user_id"))
            return
        await state.update_data(target_user_id=int(message.text.strip()))
        await state.set_state(AdminDirectSendState.waiting_text)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_text_or_caption"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminDirectSendState.waiting_text, F.text)
    async def direct_send_text(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(direct_text=message.text.strip())
        await state.set_state(AdminDirectSendState.waiting_button)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_button_or_skip"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminDirectSendState.waiting_button, F.text)
    async def direct_send_button(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        button_text = None if message.text.strip().lower() == "skip" else message.text.strip()
        await state.update_data(direct_button=button_text)
        await state.set_state(AdminDirectSendState.waiting_media)
        language = admin_language_by_user_id(message.from_user.id)
        await message.answer(
            tr(language, "admin_send_media_or_skip"),
            reply_markup=admin_cancel_keyboard(tr(language, "admin_cancel")),
        )

    @router.message(AdminDirectSendState.waiting_media, F.text)
    async def direct_send_without_media(message: Message, state: FSMContext) -> None:
        if not message.text or message.text.strip().lower() != "skip":
            return
        data = await state.get_data()
        language = admin_language_by_user_id(message.from_user.id)
        try:
            sent = await send_to_user(
                data["target_user_id"],
                data["direct_text"],
                None,
                None,
                data.get("direct_button"),
                message.bot,
            )
        except Exception:
            logger.exception("direct_send_failed chat_id=%s media_kind=text", data["target_user_id"])
            raise
        await state.clear()
        if not sent:
            await message.answer(
                tr(language, "admin_target_user_blocked_bot"),
                reply_markup=admin_menu_markup(language),
            )
            return
        await message.answer(tr(language, "admin_message_sent"), reply_markup=admin_menu_markup(language))

    @router.message(AdminDirectSendState.waiting_media, F.photo)
    async def direct_send_photo(message: Message, state: FSMContext) -> None:
        await state.update_data(direct_media_kind="photo", direct_media_file_id=message.photo[-1].file_id)
        await state.set_state(AdminDirectSendState.waiting_stars)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_unlock_photo_price"))

    @router.message(AdminDirectSendState.waiting_media, F.video)
    async def direct_send_video(message: Message, state: FSMContext) -> None:
        await state.update_data(direct_media_kind="video", direct_media_file_id=message.video.file_id)
        await state.set_state(AdminDirectSendState.waiting_stars)
        await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_unlock_video_price"))

    @router.message(AdminDirectSendState.waiting_stars, F.text)
    async def direct_send_stars(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer(tr(admin_language_by_user_id(message.from_user.id), "admin_send_numeric_stars_amount"))
            return
        data = await state.get_data()
        stars_price = int(message.text.strip())
        language = admin_language_by_user_id(message.from_user.id)
        try:
            sent = await send_paid_media_to_user(
                chat_id=data["target_user_id"],
                text=data["direct_text"],
                media_kind=data["direct_media_kind"],
                media_file_id=data["direct_media_file_id"],
                star_count=stars_price,
                button=data.get("direct_button"),
                bot=message.bot,
            )
        except Exception:
            logger.exception("direct_send_failed chat_id=%s media_kind=%s", data["target_user_id"], data["direct_media_kind"])
            raise
        if not sent:
            await state.clear()
            await message.answer(
                tr(language, "admin_target_user_blocked_bot"),
                reply_markup=admin_menu_markup(language),
            )
            return
        target_user = User.get_or_none(User.telegram_id == data["target_user_id"])
        if target_user:
            CustomRequestService.mark_delivered(
                user=target_user,
                media_type=data["direct_media_kind"],
                stars_price=stars_price,
                caption_text=data["direct_text"],
            )
        await state.clear()
        await message.answer(tr(language, "admin_paid_media_sent"), reply_markup=admin_menu_markup(language))

    return router
