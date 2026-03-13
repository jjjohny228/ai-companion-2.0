from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import FSInputFile, Message

from app.config import Settings
from app.keyboards.common import main_menu_keyboard, subscription_keyboard, subscription_plans_keyboard
from app.services.avatar_service import AvatarService
from app.services.billing_service import BillingService
from app.services.dialog_service import DialogService
from app.services.photo_delivery_service import PhotoDeliveryService
from app.services.subscription_gate import SubscriptionGateService
from app.services.user_service import UserService
from app.texts import format_plans, tr


def build_router(settings: Settings, dialog_service: DialogService) -> Router:
    router = Router()
    photo_delivery_service = PhotoDeliveryService(settings)

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
            await send_subscription_plans(message, language)
            return

        answer, pending = await dialog_service.answer(user, profile, avatar, message.text)
        BillingService.consume_avatar_message(profile, settings.default_free_avatar_messages)
        await message.answer(
            answer,
            reply_markup=main_menu_keyboard(
                tr(language, "menu_chat"),
                tr(language, "menu_avatar"),
                tr(language, "menu_language"),
                tr(language, "menu_subscription"),
                tr(language, "menu_gift"),
            ),
        )
        if pending.lite_path:
            await message.answer_photo(FSInputFile(pending.lite_path))
        if pending.premium_photo:
            await photo_delivery_service.send_paid_with_delay(
                message=message,
                avatar=avatar,
                language=language,
                photo_path=pending.premium_photo.photo_path,
                star_count=pending.premium_photo.stars_price,
                payload=f"premium_photo:{pending.premium_photo.id}",
            )

    return router
