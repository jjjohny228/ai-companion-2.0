from __future__ import annotations

import asyncio
import math

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import FSInputFile, Message

from app.config import Settings
from app.keyboards.common import main_menu_keyboard, subscription_keyboard, subscription_plans_keyboard
from app.services.avatar_service import AvatarService
from app.services.billing_service import BillingService
from app.services.custom_request_service import CustomRequestService
from app.services.dialog_service import DialogService
from app.services.photo_delivery_service import PhotoDeliveryService
from app.services.subscription_gate import SubscriptionGateService
from app.services.user_service import UserService
from app.texts import format_plans, tr


def build_router(settings: Settings, dialog_service: DialogService) -> Router:
    router = Router()
    photo_delivery_service = PhotoDeliveryService(settings)

    async def send_subscription_plans(message: Message, language: str) -> None:
        _, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        effective_limit = BillingService.effective_free_limit(
            profile, settings.default_free_avatar_messages, settings.channel_bonus_messages
        )
        available_messages = BillingService.available_messages(profile, effective_limit)
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

    async def send_channel_bonus_offer(message: Message, language: str) -> None:
        channels = SubscriptionGateService.active_channels()
        if channels:
            await message.answer(
                tr(language, "channel_bonus_offer"),
                reply_markup=subscription_keyboard(channels, tr(language, "check_subscription")),
            )
        await send_subscription_plans(message, language)

    async def simulate_typing(bot: Bot, chat_id: int, text: str) -> None:
        total_delay = max(1.2, min(8.0, math.ceil(len(text) / 18)))
        elapsed = 0.0
        while elapsed < total_delay:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            chunk = min(4.0, total_delay - elapsed)
            await asyncio.sleep(chunk)
            elapsed += chunk

    @router.message(F.text)
    async def chat_handler(message: Message, bot: Bot) -> None:
        if not message.from_user or not message.text:
            return
        if message.text.startswith("/"):
            return
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        language = profile.language

        avatar = profile.selected_avatar
        if not avatar or not avatar.is_active:
            await message.answer(tr(language, "no_avatar_selected"))
            return

        effective_limit = BillingService.effective_free_limit(
            profile, settings.default_free_avatar_messages, settings.channel_bonus_messages
        )
        if not BillingService.can_send_avatar_message(profile, effective_limit):
            if not profile.channel_bonus_granted and SubscriptionGateService.active_channels():
                await send_channel_bonus_offer(message, language)
            else:
                await send_subscription_plans(message, language)
            return

        answer, pending = await dialog_service.answer(user, profile, avatar, message.text)
        BillingService.consume_avatar_message(profile, effective_limit)
        await simulate_typing(bot, message.chat.id, answer)
        await message.answer(
            answer,
            reply_markup=main_menu_keyboard(
                tr(language, "menu_chat"),
                tr(language, "menu_avatar"),
                tr(language, "menu_language"),
                tr(language, "menu_subscription"),
                tr(language, "menu_gift"),
                tr(language, "menu_premium"),
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
        if pending.custom_request:
            media_type, description = pending.custom_request
            custom_request = CustomRequestService.create(user, avatar, media_type, description)
            for admin_id in settings.admin_ids:
                await bot.send_message(
                    admin_id,
                    "\n".join(
                        [
                            "New custom request",
                            f"Type: {media_type}",
                            f"User ID: {user.telegram_id}",
                            f"Avatar: {avatar.display_name}",
                            f"Price: {custom_request.stars_price} Stars",
                            f"Description: {description}",
                        ]
                    ),
                )

    return router
