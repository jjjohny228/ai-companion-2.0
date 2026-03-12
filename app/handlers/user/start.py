from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, ChatJoinRequest, Message

from app.config import Settings
from app.keyboards.common import (
    avatar_keyboard,
    language_keyboard,
    main_menu_keyboard,
    subscription_keyboard,
    subscription_plans_keyboard,
)
from app.services.avatar_service import AvatarService
from app.services.billing_service import BillingService
from app.services.subscription_gate import SubscriptionGateService
from app.services.user_service import UserService
from app.texts import format_channels_message, format_plans, tr


def build_router(settings: Settings) -> Router:
    router = Router()

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
        await callback.message.answer(
            f"{tr(language, 'language_updated')}\n\n{tr(language, 'choose_avatar')}",
            reply_markup=avatar_keyboard(avatars),
        )
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

    @router.callback_query(F.data.startswith("avatar:"))
    async def avatar_handler(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.message:
            return
        _, avatar_id = callback.data.split(":", 1)
        _, profile = UserService.get_or_create_from_telegram(callback.from_user, settings.admin_ids)
        avatar = AvatarService.get_active(int(avatar_id))
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
            ),
        )
        await callback.answer()

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
        await message.answer(tr(profile.language, "choose_avatar"), reply_markup=avatar_keyboard(AvatarService.list_active()))

    @router.message(F.text.in_({"Subscription", "Подписка", "Пiдписка"}))
    async def subscription_menu(message: Message) -> None:
        if not message.from_user:
            return
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        language = profile.language
        plan_rows = [(plan.code, f"{plan.title} - {plan.stars_price} Stars") for plan in BillingService.list_plans()]
        await message.answer(format_plans(language), reply_markup=subscription_plans_keyboard(plan_rows))

    return router
