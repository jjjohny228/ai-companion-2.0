from __future__ import annotations

from aiogram import F, Router
from aiogram.types import LabeledPrice, Message, PaidMediaPurchased, PreCheckoutQuery

from app.config import Settings
from app.db.models import Avatar, PremiumPhotoPurchase
from app.services.billing_service import BillingService
from app.services.gift_service import GiftService
from app.services.photo_delivery_service import PhotoDeliveryService
from app.services.premium_photo_service import PremiumPhotoService
from app.services.user_service import UserService


def build_router(settings: Settings) -> Router:
    router = Router()
    photo_delivery_service = PhotoDeliveryService(settings)

    @router.callback_query(F.data.startswith("plan:"))
    async def buy_plan(callback) -> None:
        if not callback.from_user or not callback.message:
            return
        _, plan_code = callback.data.split(":", 1)
        plan = BillingService.get_plan(plan_code)
        if not plan:
            await callback.answer("Plan not found", show_alert=True)
            return
        await callback.message.answer_invoice(
            title=plan.title,
            description=f"{plan.bot_message_quota} bot replies",
            payload=plan.code,
            currency="XTR",
            prices=[LabeledPrice(label=plan.title, amount=plan.stars_price)],
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("gift:"))
    async def buy_gift(callback) -> None:
        if not callback.from_user or not callback.message:
            return
        gift_id = int(callback.data.split(":")[1])
        gift = GiftService.get_active(gift_id)
        user, profile = UserService.get_or_create_from_telegram(callback.from_user, settings.admin_ids)
        avatar = profile.selected_avatar
        if not gift:
            await callback.answer("Gift not found", show_alert=True)
            return
        if not avatar:
            await callback.answer("Choose avatar first", show_alert=True)
            return
        await callback.message.answer_invoice(
            title=gift.title,
            description=gift.description,
            payload=GiftService.build_payload(gift.id, avatar.id),
            currency="XTR",
            prices=[LabeledPrice(label=gift.title, amount=gift.stars_price)],
        )
        await callback.answer()

    @router.pre_checkout_query()
    async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
        await pre_checkout_query.answer(ok=True)

    @router.message(F.successful_payment)
    async def successful_payment(message: Message) -> None:
        if not message.from_user or not message.successful_payment:
            return
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        gift_payload = GiftService.parse_payload(message.successful_payment.invoice_payload)
        if gift_payload:
            gift_id, avatar_id = gift_payload
            gift = GiftService.get_active(gift_id)
            avatar = Avatar.get_or_none(Avatar.id == avatar_id)
            if not gift or not avatar:
                await message.answer("Unknown gift.")
                return
            purchase = GiftService.register_purchase(
                user=user,
                avatar=avatar,
                gift=gift,
                telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
                provider_payment_charge_id=message.successful_payment.provider_payment_charge_id,
            )
            await message.answer("Gift sent successfully.")
            if purchase.rewarded_premium_photo_id and purchase.rewarded_premium_photo:
                await photo_delivery_service.send_with_delay(
                    message=message,
                    avatar=avatar,
                    language=profile.language,
                    photo_path=purchase.rewarded_premium_photo.photo_path,
                    mode="gift",
                )
            else:
                await message.answer("This gift does not unlock a premium photo yet.")
            return

        plan = BillingService.get_plan(message.successful_payment.invoice_payload)
        if plan:
            BillingService.register_successful_payment(
                user=user,
                profile=profile,
                plan=plan,
                telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
                provider_payment_charge_id=message.successful_payment.provider_payment_charge_id,
            )
            await message.answer(f"Payment successful. Balance added: {plan.bot_message_quota}")
            return
        await message.answer("Unknown payment payload.")

    @router.purchased_paid_media()
    async def purchased_paid_media_handler(event: PaidMediaPurchased) -> None:
        user, _ = UserService.get_or_create_from_telegram(event.from_user, settings.admin_ids)
        payload = event.paid_media_payload
        if not payload.startswith("premium_photo:"):
            return
        photo_id = int(payload.split(":")[1])
        premium_photo = PremiumPhotoService.get_active(photo_id)
        if not premium_photo:
            return
        PremiumPhotoPurchase.get_or_create(
            telegram_payment_charge_id=f"paid_media:{user.telegram_id}:{photo_id}",
            defaults={
                "user": user,
                "avatar": premium_photo.avatar,
                "premium_photo": premium_photo,
                "provider_payment_charge_id": None,
                "stars_amount": premium_photo.stars_price,
                "status": "paid",
            },
        )

    return router
