from __future__ import annotations

import shutil
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from app.config import Settings
from app.db.models import Avatar, Channel
from app.keyboards.common import admin_menu_keyboard
from app.services.stats_service import StatsService
from app.services.user_service import UserService
from app.states.admin import AdminAvatarUploadState
from app.texts import tr
from app.utils.files import ensure_avatar_dirs


def build_router(settings: Settings) -> Router:
    router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id in settings.admin_ids

    async def set_upload_target(state: FSMContext, avatar_id: int) -> None:
        await state.set_state(AdminAvatarUploadState.selecting_upload_target)
        await state.update_data(avatar_id=avatar_id)

    async def get_upload_target(state: FSMContext) -> int | None:
        data = await state.get_data()
        avatar_id = data.get("avatar_id")
        return int(avatar_id) if avatar_id else None

    async def resolve_avatar_for_upload(message: Message, state: FSMContext) -> Avatar | None:
        if message.caption:
            if message.caption.startswith("avatar:"):
                raw_avatar_id = message.caption.split(":", 1)[1].strip()
                if raw_avatar_id.isdigit():
                    return Avatar.get_or_none(Avatar.id == int(raw_avatar_id))
            if message.caption.startswith("avatar_zip:"):
                raw_avatar_id = message.caption.split(":", 1)[1].strip()
                if raw_avatar_id.isdigit():
                    return Avatar.get_or_none(Avatar.id == int(raw_avatar_id))
        target_id = await get_upload_target(state)
        if not target_id:
            return None
        return Avatar.get_or_none(Avatar.id == target_id)

    @router.message(Command("admin"))
    async def admin_menu(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(tr(profile.language, "admin_menu"), reply_markup=admin_menu_keyboard())

    @router.message(F.text.in_({"Stats day", "Stats month", "Stats all"}))
    async def stats_handler(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id) or not message.text:
            return
        period = "day" if message.text == "Stats day" else "month" if message.text == "Stats month" else "all"
        stats = StatsService.collect(period)
        await message.answer(
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

    @router.message(F.text == "Add avatar")
    async def add_avatar_help(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await message.answer(
            "Create avatar via /add_avatar slug | name | description | system_prompt\n"
            "After that you can send photos or a .zip without caption.\n"
            "You can switch current upload target with /use_avatar 12"
        )

    @router.message(Command("add_avatar"))
    async def add_avatar(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id) or not message.text:
            return
        payload = message.text.replace("/add_avatar", "", 1).strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) != 4:
            await message.answer("Format: /add_avatar slug | name | description | system_prompt")
            return
        slug, name, description, system_prompt = parts
        avatar = Avatar.create(
            slug=slug,
            display_name=name,
            description=description,
            system_prompt=system_prompt,
        )
        ensure_avatar_dirs(settings.assets_dir, avatar.id)
        await set_upload_target(state, avatar.id)
        await message.answer(
            f"Avatar created: id={avatar.id}\n"
            f"Current upload target set to avatar {avatar.id}. Now you can send photos or a .zip without caption."
        )

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
        await set_upload_target(state, avatar.id)
        await message.answer(f"Current upload target set to avatar {avatar.id} ({avatar.display_name})")

    @router.message(Command("clear_avatar_context"))
    async def clear_avatar_context(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer("Avatar upload context cleared.")

    @router.message(Command("toggle_avatar"))
    async def toggle_avatar(message: Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id) or not message.text:
            return
        payload = message.text.replace("/toggle_avatar", "", 1).strip()
        if not payload.isdigit():
            await message.answer("Format: /toggle_avatar 12")
            return
        avatar = Avatar.get_or_none(Avatar.id == int(payload))
        if not avatar:
            await message.answer("Avatar not found.")
            return
        avatar.is_active = not avatar.is_active
        avatar.save()
        await message.answer(f"Avatar {avatar.id} active={avatar.is_active}")

    @router.message(F.photo)
    async def upload_avatar_photo(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        avatar = await resolve_avatar_for_upload(message, state)
        if not avatar:
            await message.answer("Avatar is not selected. Use /use_avatar 12 or caption avatar:12")
            return
        photo = message.photo[-1]
        avatar_dir = ensure_avatar_dirs(settings.assets_dir, avatar.id) / "photos"
        destination = avatar_dir / f"{photo.file_unique_id}.jpg"
        file = await message.bot.get_file(photo.file_id)
        await message.bot.download_file(file.file_path, destination=destination)
        await set_upload_target(state, avatar.id)
        await message.answer(f"Photo saved to avatar {avatar.id}")

    @router.message(F.document)
    async def upload_avatar_zip(message: Message, state: FSMContext) -> None:
        if not message.from_user or not is_admin(message.from_user.id):
            return
        document = message.document
        if not document:
            return
        if not document.file_name or not document.file_name.lower().endswith(".zip"):
            return
        avatar = await resolve_avatar_for_upload(message, state)
        if not avatar:
            await message.answer("Avatar is not selected. Use /use_avatar 12 or caption avatar_zip:12")
            return
        avatar_dir = ensure_avatar_dirs(settings.assets_dir, avatar.id)
        zip_path = avatar_dir / document.file_name
        file = await message.bot.get_file(document.file_id)
        await message.bot.download_file(file.file_path, destination=zip_path)
        shutil.unpack_archive(str(zip_path), str(avatar_dir / "photos"))
        zip_path.unlink(missing_ok=True)
        await set_upload_target(state, avatar.id)
        await message.answer(f"Zip extracted for avatar {avatar.id}")

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
