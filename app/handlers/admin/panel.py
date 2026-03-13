from __future__ import annotations

import shutil
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings
from app.db.models import Avatar, Channel, Gift
from app.keyboards.common import admin_avatar_keyboard, admin_gift_keyboard, admin_menu_keyboard, admin_stats_keyboard
from app.services.stats_service import StatsService
from app.services.user_service import UserService
from app.states.admin import (
    AdminAvatarCreateState,
    AdminAvatarEditState,
    AdminAvatarUploadState,
    AdminGiftCreateState,
    AdminGiftEditState,
    AdminPremiumPhotoState,
)
from app.texts import tr
from app.utils.files import ensure_avatar_dirs
from app.services.premium_photo_service import PremiumPhotoService


def build_router(settings: Settings) -> Router:
    router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id in settings.admin_ids

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

    def gifts_list_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for gift in Gift.select().order_by(Gift.stars_price, Gift.id):
            status = "ON" if gift.is_active else "OFF"
            builder.button(text=f"{gift.title} [{status}]", callback_data=f"admin_gift:open:{gift.id}")
        builder.adjust(1)
        return builder.as_markup()

    def avatar_edit_keyboard(avatar_id: int) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="Main photo", callback_data=f"admin_avatar:edit:{avatar_id}:main_photo")
        builder.button(text="Description", callback_data=f"admin_avatar:edit:{avatar_id}:description")
        builder.button(text="System prompt", callback_data=f"admin_avatar:edit:{avatar_id}:system_prompt")
        builder.button(text="Upload lite photos", callback_data=f"admin_avatar:bucket:{avatar_id}:photos")
        builder.button(text="Upload premium photos", callback_data=f"admin_avatar:bucket:{avatar_id}:premium")
        builder.button(text="Toggle active", callback_data=f"admin_avatar:toggle:{avatar_id}")
        builder.adjust(1)
        return builder.as_markup()

    def skip_main_photo_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="Skip", callback_data="admin_avatar:create:skip_main_photo")
        return builder.as_markup()

    def continue_media_keyboard(prefix: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="Skip", callback_data=f"{prefix}:skip")
        builder.button(text="Done", callback_data=f"{prefix}:done")
        builder.adjust(2)
        return builder.as_markup()

    def skip_gift_photo_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="Skip", callback_data="admin_gift:create:skip_photo")
        return builder.as_markup()

    def gift_edit_keyboard(gift_id: int) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="Photo", callback_data=f"admin_gift:edit:{gift_id}:photo")
        builder.button(text="Title", callback_data=f"admin_gift:edit:{gift_id}:title")
        builder.button(text="Description", callback_data=f"admin_gift:edit:{gift_id}:description")
        builder.button(text="Price", callback_data=f"admin_gift:edit:{gift_id}:price")
        builder.button(text="Toggle active", callback_data=f"admin_gift:toggle:{gift_id}")
        builder.adjust(1)
        return builder.as_markup()

    def avatar_bucket_dir(avatar_id: int, bucket: str) -> Path:
        return ensure_avatar_dirs(settings.assets_dir, avatar_id) / bucket

    async def start_premium_photo_metadata_flow(state: FSMContext, avatar_id: int, saved_path: Path) -> None:
        await state.update_data(premium_avatar_id=avatar_id, pending_premium_photo_path=str(saved_path))
        await state.set_state(AdminPremiumPhotoState.waiting_price)

    @router.message(Command("admin"))
    async def admin_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(tr(profile.language, "admin_menu"), reply_markup=admin_menu_keyboard())

    @router.message(F.text == "Back to admin")
    async def back_to_admin(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Admin menu", reply_markup=admin_menu_keyboard())

    @router.message(F.text == "Statistics")
    async def statistics_menu(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await message.answer("Choose period for statistics:", reply_markup=admin_stats_keyboard())

    @router.callback_query(F.data.startswith("admin_stats:"))
    async def statistics_callback(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        period = callback.data.split(":", 1)[1]
        stats = StatsService.collect(period)
        await callback.message.answer(
            "\n".join(
                [
                    f"Period: {period}",
                    f"Users: {stats['users']}",
                    f"Messages: {stats['messages']}",
                    f"Payments: {stats['payments']}",
                    f"Stars: {stats['stars']}",
                    f"Top avatar messages: {stats['top_avatar_messages']}",
                ]
            )
        )
        await callback.answer()

    @router.message(F.text == "Avatars")
    async def avatars_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Avatar management", reply_markup=admin_avatar_keyboard())

    @router.message(F.text == "Gifts")
    async def gifts_menu(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Gift management", reply_markup=admin_gift_keyboard())

    @router.message(F.text == "Add avatar")
    async def start_add_avatar(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminAvatarCreateState.waiting_slug)
        await message.answer("Send avatar slug.")

    @router.message(AdminAvatarCreateState.waiting_slug, F.text)
    async def create_avatar_slug(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(slug=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_name)
        await message.answer("Send avatar display name.")

    @router.message(AdminAvatarCreateState.waiting_name, F.text)
    async def create_avatar_name(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(name=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_description)
        await message.answer("Send avatar description.")

    @router.message(AdminAvatarCreateState.waiting_description, F.text)
    async def create_avatar_description(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(description=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_system_prompt)
        await message.answer("Send avatar system prompt.")

    @router.message(AdminAvatarCreateState.waiting_system_prompt, F.text)
    async def create_avatar_system_prompt(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(system_prompt=message.text.strip())
        await state.set_state(AdminAvatarCreateState.waiting_main_photo)
        await message.answer(
            "Send main photo for this avatar, or press Skip.",
            reply_markup=skip_main_photo_keyboard(),
        )

    @router.callback_query(F.data == "admin_avatar:create:skip_main_photo")
    async def skip_main_photo(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        data = await state.get_data()
        avatar = Avatar.create(
            slug=data["slug"],
            display_name=data["name"],
            description=data["description"],
            system_prompt=data["system_prompt"],
        )
        ensure_avatar_dirs(settings.assets_dir, avatar.id)
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarCreateState.waiting_lite_media)
        await callback.message.answer(
            f"Avatar created: id={avatar.id}\n"
            "Now send lite photos or .zip for this avatar, or press Skip / Done.",
            reply_markup=continue_media_keyboard("admin_avatar:create:lite"),
        )
        await callback.answer()

    @router.message(AdminAvatarCreateState.waiting_main_photo, F.photo)
    async def create_avatar_main_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        avatar = Avatar.create(
            slug=data["slug"],
            display_name=data["name"],
            description=data["description"],
            system_prompt=data["system_prompt"],
        )
        path = avatar_main_photo_path(avatar.id)
        await save_telegram_photo(message, path)
        avatar.main_photo_path = str(path)
        avatar.save()
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarCreateState.waiting_lite_media)
        await message.answer(
            f"Avatar created: id={avatar.id}\nMain photo saved.\n"
            "Now send lite photos or .zip for this avatar, or press Skip / Done.",
            reply_markup=continue_media_keyboard("admin_avatar:create:lite"),
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
        await callback.message.answer(
            "Now send premium photos or .zip for this avatar, or press Skip / Done.",
            reply_markup=continue_media_keyboard("admin_avatar:create:premium"),
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
        await callback.message.answer(
            f"Avatar setup finished for avatar {avatar.id if avatar else avatar_id}. "
            "Default upload target switched to lite photos."
        )
        await callback.answer()

    @router.message(F.text == "Edit avatars")
    async def edit_avatars(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Choose avatar to edit:", reply_markup=avatars_list_keyboard())

    @router.message(F.text == "Add gift")
    async def start_add_gift(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.set_state(AdminGiftCreateState.waiting_slug)
        await message.answer("Send gift slug.")

    @router.message(AdminGiftCreateState.waiting_slug, F.text)
    async def create_gift_slug(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(gift_slug=message.text.strip())
        await state.set_state(AdminGiftCreateState.waiting_title)
        await message.answer("Send gift title.")

    @router.message(AdminGiftCreateState.waiting_title, F.text)
    async def create_gift_title(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(gift_title=message.text.strip())
        await state.set_state(AdminGiftCreateState.waiting_description)
        await message.answer("Send gift description.")

    @router.message(AdminGiftCreateState.waiting_description, F.text)
    async def create_gift_description(message: Message, state: FSMContext) -> None:
        if not message.text:
            return
        await state.update_data(gift_description=message.text.strip())
        await state.set_state(AdminGiftCreateState.waiting_price)
        await message.answer("Send gift price in Stars.")

    @router.message(AdminGiftCreateState.waiting_price, F.text)
    async def create_gift_price(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer("Send numeric price, for example 150")
            return
        await state.update_data(gift_price=int(message.text.strip()))
        await state.set_state(AdminGiftCreateState.waiting_photo)
        await message.answer("Send gift photo, or press Skip.", reply_markup=skip_gift_photo_keyboard())

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
        await callback.message.answer(f"Gift created: id={gift.id}")
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
        await message.answer(f"Gift created: id={gift.id}")

    @router.message(F.text == "Edit gifts")
    async def edit_gifts(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Choose gift to edit:", reply_markup=gifts_list_keyboard())

    @router.callback_query(F.data.startswith("admin_gift:open:"))
    async def open_gift_editor(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        gift_id = int(callback.data.split(":")[2])
        gift = Gift.get_or_none(Gift.id == gift_id)
        if not gift:
            await callback.answer("Gift not found.", show_alert=True)
            return
        await callback.message.answer(
            "\n".join(
                [
                    f"Gift #{gift.id}",
                    f"Title: {gift.title}",
                    f"Price: {gift.stars_price}",
                    f"Description: {gift.description}",
                    f"Active: {gift.is_active}",
                ]
            ),
            reply_markup=gift_edit_keyboard(gift.id),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_gift:toggle:"))
    async def toggle_gift(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            return
        gift_id = int(callback.data.split(":")[2])
        gift = Gift.get_or_none(Gift.id == gift_id)
        if not gift:
            await callback.answer("Gift not found.", show_alert=True)
            return
        gift.is_active = not gift.is_active
        gift.save()
        await callback.answer(f"Gift active={gift.is_active}")

    @router.callback_query(F.data.startswith("admin_gift:edit:"))
    async def select_gift_edit_field(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, gift_id, field_name = callback.data.split(":")
        gift = Gift.get_or_none(Gift.id == int(gift_id))
        if not gift:
            await callback.answer("Gift not found.", show_alert=True)
            return
        await state.set_state(AdminGiftEditState.waiting_value)
        await state.update_data(edit_gift_id=gift.id, edit_gift_field=field_name)
        if field_name == "photo":
            await callback.message.answer("Send new gift photo.")
        else:
            await callback.message.answer(f"Send new value for {field_name}.")
        await callback.answer()

    @router.message(AdminGiftEditState.waiting_value, F.photo)
    async def update_gift_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if data.get("edit_gift_field") != "photo":
            return
        gift = Gift.get_or_none(Gift.id == int(data["edit_gift_id"]))
        if not gift:
            await message.answer("Gift not found.")
            return
        path = gift_photo_path(gift.id)
        await save_telegram_photo(message, path)
        gift.photo_path = str(path)
        gift.save()
        await state.clear()
        await message.answer(f"Gift photo updated for gift {gift.id}")

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
                await message.answer("Send numeric price, for example 150")
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
        await message.answer(f"Gift {field_name} updated for gift {gift.id}")

    @router.callback_query(F.data.startswith("admin_avatar:open:"))
    async def open_avatar_editor(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        avatar_id = int(callback.data.split(":")[2])
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await callback.answer("Avatar not found.", show_alert=True)
            return
        await callback.message.answer(
            "\n".join(
                [
                    f"Avatar #{avatar.id}",
                    f"Name: {avatar.display_name}",
                    f"Description: {avatar.description or '-'}",
                    f"Active: {avatar.is_active}",
                ]
            ),
            reply_markup=avatar_edit_keyboard(avatar.id),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_avatar:toggle:"))
    async def toggle_avatar(callback) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id):
            return
        avatar_id = int(callback.data.split(":")[2])
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await callback.answer("Avatar not found.", show_alert=True)
            return
        avatar.is_active = not avatar.is_active
        avatar.save()
        await callback.answer(f"Avatar active={avatar.is_active}")

    @router.callback_query(F.data.startswith("admin_avatar:bucket:"))
    async def select_avatar_bucket(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, avatar_id, bucket = callback.data.split(":")
        avatar = Avatar.get_or_none(Avatar.id == int(avatar_id))
        if not avatar:
            await callback.answer("Avatar not found.", show_alert=True)
            return
        await set_upload_target(state, avatar.id, bucket)
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        label = "premium" if bucket == "premium" else "lite"
        await callback.message.answer(
            f"Upload target set to avatar {avatar.id} ({avatar.display_name}), {label} photos. "
            "Now send photos without caption." if bucket == "premium" else
            f"Upload target set to avatar {avatar.id} ({avatar.display_name}), {label} photos. Now send photos or .zip without caption."
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_avatar:edit:"))
    async def select_edit_field(callback, state: FSMContext) -> None:
        if not callback.from_user or not is_admin(callback.from_user.id) or not callback.message:
            return
        _, _, avatar_id, field_name = callback.data.split(":")
        avatar = Avatar.get_or_none(Avatar.id == int(avatar_id))
        if not avatar:
            await callback.answer("Avatar not found.", show_alert=True)
            return
        await state.set_state(AdminAvatarEditState.waiting_value)
        await state.update_data(edit_avatar_id=avatar.id, edit_field=field_name)
        if field_name == "main_photo":
            await callback.message.answer("Send new main photo for this avatar.")
        elif field_name == "description":
            await callback.message.answer("Send new description.")
        else:
            await callback.message.answer("Send new system prompt.")
        await callback.answer()

    @router.message(AdminAvatarEditState.waiting_value, F.photo)
    async def update_avatar_main_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        if data.get("edit_field") != "main_photo":
            return
        avatar = Avatar.get_or_none(Avatar.id == int(data["edit_avatar_id"]))
        if not avatar:
            await message.answer("Avatar not found.")
            return
        path = avatar_main_photo_path(avatar.id)
        await save_telegram_photo(message, path)
        avatar.main_photo_path = str(path)
        avatar.save()
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await message.answer(f"Main photo updated for avatar {avatar.id}")

    @router.message(AdminAvatarEditState.waiting_value, F.text)
    async def update_avatar_text_field(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        field_name = data.get("edit_field")
        if field_name not in {"description", "system_prompt"} or not message.text:
            return
        avatar = Avatar.get_or_none(Avatar.id == int(data["edit_avatar_id"]))
        if not avatar:
            await message.answer("Avatar not found.")
            return
        setattr(avatar, field_name, message.text.strip())
        avatar.save()
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await set_upload_target(state, avatar.id, "photos")
        await message.answer(f"{field_name} updated for avatar {avatar.id}")

    @router.message(Command("use_avatar"))
    async def use_avatar(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id) or not message.text:
            return
        payload = message.text.replace("/use_avatar", "", 1).strip()
        if not payload.isdigit():
            await message.answer("Format: /use_avatar 12")
            return
        avatar = Avatar.get_or_none(Avatar.id == int(payload))
        if not avatar:
            await message.answer("Avatar not found.")
            return
        await set_upload_target(state, avatar.id, "photos")
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await message.answer(f"Current upload target set to avatar {avatar.id} ({avatar.display_name}), lite photos")

    @router.message(Command("clear_avatar_context"))
    async def clear_avatar_context(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Avatar upload context cleared.")

    @router.message(F.photo)
    async def upload_avatar_gallery_photo(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        current_state = await state.get_state()
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
            await message.answer("Avatar not found.")
            return
        photo = message.photo[-1]
        avatar_dir = avatar_bucket_dir(avatar.id, media_bucket)
        destination = avatar_dir / f"{photo.file_unique_id}.jpg"
        await save_telegram_photo(message, destination)
        if media_bucket == "premium":
            await start_premium_photo_metadata_flow(state, avatar.id, destination)
            await message.answer("Premium photo uploaded. Send price in Stars.")
            return
        await message.answer(f"Lite photo saved to avatar {avatar.id}")

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
            await message.answer("Avatar is not selected. Use /use_avatar 12 or create a new avatar first.")
            return
        if media_bucket == "premium":
            await message.answer("Premium photos need individual price and description, so upload them one by one.")
            return
        avatar = Avatar.get_or_none(Avatar.id == avatar_id)
        if not avatar:
            await message.answer("Avatar not found.")
            return
        avatar_dir = ensure_avatar_dirs(settings.assets_dir, avatar.id)
        zip_path = avatar_dir / document.file_name
        file = await message.bot.get_file(document.file_id)
        await message.bot.download_file(file.file_path, destination=zip_path)
        shutil.unpack_archive(str(zip_path), str(avatar_bucket_dir(avatar.id, media_bucket)))
        zip_path.unlink(missing_ok=True)
        await message.answer(f"Zip extracted to lite photos for avatar {avatar.id}")

    @router.message(AdminPremiumPhotoState.waiting_price, F.text)
    async def premium_photo_price(message: Message, state: FSMContext) -> None:
        if not message.text or not message.text.strip().isdigit():
            await message.answer("Send numeric price in Stars, for example 250")
            return
        await state.update_data(pending_premium_price=int(message.text.strip()))
        data = await state.get_data()
        avatar = Avatar.get_or_none(Avatar.id == int(data["premium_avatar_id"]))
        if not avatar:
            await message.answer("Avatar not found.")
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
        await message.answer("Premium photo saved.")

    @router.message(F.text == "Add channel")
    async def add_channel_help(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await message.answer(
            "Use /add_channel chat_id | title | link | is_private(0/1) | requires_join_request(0/1)"
        )

    @router.message(Command("add_channel"))
    async def add_channel(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id) or not message.text:
            return
        payload = message.text.replace("/add_channel", "", 1).strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) != 5:
            await message.answer("Format: /add_channel chat_id | title | link | is_private(0/1) | requires_join_request(0/1)")
            return
        chat_id, title, link, is_private, join_request = parts
        channel, created = Channel.get_or_create(
            telegram_channel_id=int(chat_id),
            defaults={
                "title": title,
                "username_or_invite_link": link or None,
                "is_private": is_private == "1",
                "requires_join_request": join_request == "1",
                "is_active": True,
            },
        )
        if not created:
            channel.title = title
            channel.username_or_invite_link = link or None
            channel.is_private = is_private == "1"
            channel.requires_join_request = join_request == "1"
            channel.is_active = True
            channel.save()
        await message.answer(f"Channel saved: {channel.title}")

    @router.message(F.text == "Download DB")
    async def download_db(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        db_file = Path(settings.db_path)
        if not db_file.exists():
            await message.answer("Database file not found.")
            return
        await message.answer_document(FSInputFile(db_file), caption="SQLite database")

    return router
