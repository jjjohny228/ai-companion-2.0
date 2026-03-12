from __future__ import annotations

from aiogram import F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from app.config import Settings
from app.services.billing_service import BillingService
from app.services.user_service import UserService


def build_router(settings: Settings) -> Router:
    router = Router()

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

    @router.pre_checkout_query()
    async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
        await pre_checkout_query.answer(ok=True)

    @router.message(F.successful_payment)
    async def successful_payment(message: Message) -> None:
        if not message.from_user or not message.successful_payment:
            return
        user, profile = UserService.get_or_create_from_telegram(message.from_user, settings.admin_ids)
        plan = BillingService.get_plan(message.successful_payment.invoice_payload)
        if not plan:
            await message.answer("Unknown plan.")
            return
        BillingService.register_successful_payment(
            user=user,
            profile=profile,
            plan=plan,
            telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
            provider_payment_charge_id=message.successful_payment.provider_payment_charge_id,
        )
        await message.answer(f"Payment successful. Balance added: {plan.bot_message_quota}")

    return router
