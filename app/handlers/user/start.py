from __future__ import annotations

from pathlib import Path
from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, ChatJoinRequest, FSInputFile, Message

from app.config import Settings
from app.keyboards.common import (
    avatar_keyboard,
    gifts_keyboard,
    language_keyboard,
    main_menu_keyboard,
    subscription_keyboard,
    subscription_plans_keyboard,
)
from app.services.avatar_service import AvatarService
from app.services.billing_service import BillingService
from app.services.gift_service import GiftService
from app.services.subscription_gate import SubscriptionGateService
from app.services.user_service import UserService
from app.texts import format_channels_message, format_plans, tr


def build_router(settings: Settings) -> Router:
    router = Router()

    async def send_avatar_card(target_message: Message, avatar_id: int, language: str) -> None:
        avatar = AvatarService.get_active(avatar_id)
        if not avatar:
            await target_message.answer("Avatar not found.")
            return
        has_prev, has_next = AvatarService.get_navigation_flags(avatar.id)
        caption = f"<b>{escape(avatar.display_name)}</b>\n{escape(avatar.description or '')}".strip()
        if avatar.main_photo_path and Path(avatar.main_photo_path).exists():
            await target_message.answer_photo(
                FSInputFile(avatar.main_photo_path),
                caption=caption,
                reply_markup=avatar_keyboard(avatar, has_prev, has_next),
            )
        else:
            await target_message.answer(caption, reply_markup=avatar_keyboard(avatar, has_prev, has_next))

    async def send_subscription_plans(message: Message, language: str) -> None:
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        available_messages = BillingService.available_messages(profile, settings.default_free_avatar_messages)
        plan_rows = [(plan.code, f"{plan.title} - {plan.stars_price} Stars") for plan in BillingService.list_plans()]
        if settings.subscription_media_path and settings.subscription_media_path.exists():
            await message.answer_photo(
                FSInputFile(settings.subscription_media_path),
                caption=format_plans(language, available_messages),
                reply_markup=subscription_plans_keyboard(plan_rows),
            )
        else:
            await message.answer(
                format_plans(language, available_messages),
                reply_markup=subscription_plans_keyboard(plan_rows),
            )

    @router.message(F.text == "/start")
    async def start_handler(message: Message, bot: Bot) -> None:
        if not message.from_user:
            return
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        language = profile.language
        channels = SubscriptionGateService.active_channels()
        if channels:
            await message.answer(
                format_channels_message(language, SubscriptionGateService.channel_links()),
                reply_markup=subscription_keyboard(channels, tr(language, "check_subscription")),
            )
            return
        if not profile.selected_avatar_id:
            await message.answer(tr(language, "choose_language"), reply_markup=language_keyboard())
            return
        await message.answer(
            tr(language, "main_menu"),
            reply_markup=main_menu_keyboard(
                tr(language, "menu_chat"),
                tr(language, "menu_avatar"),
                tr(language, "menu_language"),
                tr(language, "menu_subscription"),
                tr(language, "menu_gift"),
            ),
        )

    @router.callback_query(F.data == "subscription:check")
    async def check_subscription_handler(callback: CallbackQuery, bot: Bot) -> None:
        if not callback.from_user or not callback.message:
            return
        user, profile = UserService.get_or_create_from_telegram(callback.from_user, settings.admin_ids)
        is_allowed = await SubscriptionGateService.check_all(bot, callback.from_user.id)
        language = profile.language
        if not is_allowed:
            await callback.message.answer(tr(language, "subscription_missing"))
            await callback.answer()
            return
        if not profile.selected_avatar_id:
            await callback.message.answer(tr(language, "choose_language"), reply_markup=language_keyboard())
        else:
            await callback.message.answer(
                tr(language, "subscription_ok"),
                reply_markup=main_menu_keyboard(
                    tr(language, "menu_chat"),
                    tr(language, "menu_avatar"),
                    tr(language, "menu_language"),
                    tr(language, "menu_subscription"),
                    tr(language, "menu_gift"),
                ),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("language:"))
    async def language_handler(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.message:
            return
        _, language = callback.data.split(":", 1)
        user, profile = UserService.get_or_create_from_telegram(callback.from_user, settings.admin_ids)
        UserService.set_language(profile, language)
        avatars = AvatarService.list_active()
        await callback.message.answer(f"{tr(language, 'language_updated')}\n\n{tr(language, 'choose_avatar')}")
        if avatars:
            await send_avatar_card(callback.message, avatars[0].id, language)
        await callback.answer()

    @router.callback_query(F.data.startswith("avatar:choose:"))
    async def avatar_handler(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.message:
            return
        avatar_id = int(callback.data.split(":")[2])
        _, profile = UserService.get_or_create_from_telegram(callback.from_user, settings.admin_ids)
        avatar = AvatarService.get_active(avatar_id)
        language = profile.language
        if not avatar:
            await callback.answer("Avatar not found", show_alert=True)
            return
        AvatarService.select_avatar(profile, avatar)
        await callback.message.answer(
            tr(language, "avatar_selected"),
            reply_markup=main_menu_keyboard(
                tr(language, "menu_chat"),
                tr(language, "menu_avatar"),
                tr(language, "menu_language"),
                tr(language, "menu_subscription"),
                tr(language, "menu_gift"),
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("avatar:nav:"))
    async def avatar_navigation_handler(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.message:
            return
        _, _, current_avatar_id, direction = callback.data.split(":")
        _, profile = UserService.get_or_create_from_telegram(callback.from_user, settings.admin_ids)
        offset = -1 if direction == "prev" else 1
        next_avatar = AvatarService.get_active_by_offset(int(current_avatar_id), offset)
        if not next_avatar:
            await callback.answer()
            return
        await send_avatar_card(callback.message, next_avatar.id, profile.language)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()

    @router.chat_join_request()
    async def join_request_handler(join_request: ChatJoinRequest) -> None:
        user, _ = UserService.get_or_create_from_telegram(join_request.from_user, settings.admin_ids)
        channel = next(
            (
                item for item in SubscriptionGateService.active_channels()
                if item.telegram_channel_id == join_request.chat.id
            ),
            None,
        )
        if channel:
            SubscriptionGateService.register_join_request(user, channel)

    @router.message(F.text.in_({"Language", "Язык", "Мова"}))
    async def change_language(message: Message) -> None:
        if not message.from_user:
            return
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await message.answer(tr(profile.language, "choose_language"), reply_markup=language_keyboard())

    @router.message(F.text.in_({"Change avatar", "Сменить аватара", "Змiнити аватара"}))
    async def change_avatar(message: Message) -> None:
        if not message.from_user:
            return
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        avatars = AvatarService.list_active()
        await message.answer(tr(profile.language, "choose_avatar"))
        if avatars:
            await send_avatar_card(message, avatars[0].id, profile.language)

    @router.message(F.text.in_({"Subscription", "Подписка", "Пiдписка"}))
    async def subscription_menu(message: Message) -> None:
        if not message.from_user:
            return
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        await send_subscription_plans(message, profile.language)

    @router.message(F.text.in_({"Send gift", "Подарок", "Подарунок"}))
    async def gift_menu(message: Message) -> None:
        if not message.from_user:
            return
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        gifts = GiftService.list_active()
        if not gifts:
            await message.answer("No gifts available yet.")
            return
        await message.answer(tr(profile.language, "gift_choose"), reply_markup=gifts_keyboard(gifts))

    return router
