from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import FSInputFile, Message

from app.config import Settings
from app.keyboards.common import main_menu_keyboard, subscription_keyboard
from app.services.avatar_service import AvatarService
from app.services.billing_service import BillingService
from app.services.dialog_service import DialogService
from app.services.subscription_gate import SubscriptionGateService
from app.services.user_service import UserService
from app.texts import format_plans, tr


def build_router(settings: Settings, dialog_service: DialogService) -> Router:
    router = Router()

    @router.message(F.text)
    async def chat_handler(message: Message, bot: Bot) -> None:
        if not message.from_user or not message.text:
            return
        if message.text.startswith("/"):
            return
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        language = profile.language

        if not await SubscriptionGateService.check_all(bot, message.from_user.id):
            channels = SubscriptionGateService.active_channels()
            await message.answer(
                tr(language, "subscription_required"),
                reply_markup=subscription_keyboard(channels, tr(language, "check_subscription")),
            )
            return

        avatar = profile.selected_avatar
        if not avatar or not avatar.is_active:
            await message.answer(tr(language, "no_avatar_selected"))
            return

        if not BillingService.can_send_avatar_message(profile, settings.default_free_avatar_messages):
            await message.answer(format_plans(language))
            return

        answer, photo_path = await dialog_service.answer(user, profile, avatar, message.text)
        BillingService.consume_avatar_message(profile, settings.default_free_avatar_messages)
        await message.answer(
            answer,
            reply_markup=main_menu_keyboard(
                tr(language, "menu_chat"),
                tr(language, "menu_avatar"),
                tr(language, "menu_language"),
                tr(language, "menu_subscription"),
            ),
        )

        if photo_path:
            await message.answer_photo(FSInputFile(photo_path), caption=avatar.display_name)

    return router
