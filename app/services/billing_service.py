from __future__ import annotations

from datetime import datetime

from app.constants import SUBSCRIPTION_PLANS, SubscriptionPlan
from app.db.models import Payment, User, UserProfile


class BillingService:
    @staticmethod
    def get_plan(plan_code: str) -> SubscriptionPlan | None:
        return next((plan for plan in SUBSCRIPTION_PLANS if plan.code == plan_code), None)

    @staticmethod
    def list_plans() -> tuple[SubscriptionPlan, ...]:
        return SUBSCRIPTION_PLANS

    @staticmethod
    def can_send_avatar_message(profile: UserProfile, free_limit: int) -> bool:
        return profile.paid_message_balance > 0 or profile.free_messages_used < free_limit

    @staticmethod
    def consume_avatar_message(profile: UserProfile, free_limit: int) -> None:
        if profile.paid_message_balance > 0:
            profile.paid_message_balance -= 1
        elif profile.free_messages_used < free_limit:
            profile.free_messages_used += 1
        profile.updated_at = datetime.utcnow()
        profile.save()

    @staticmethod
    def register_successful_payment(
        user: User,
        profile: UserProfile,
        plan: SubscriptionPlan,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> Payment:
        payment, created = Payment.get_or_create(
            telegram_payment_charge_id=telegram_payment_charge_id,
            defaults={
                "user": user,
                "plan_code": plan.code,
                "message_quota": plan.bot_message_quota,
                "stars_amount": plan.stars_price,
                "provider_payment_charge_id": provider_payment_charge_id,
                "status": "paid",
            },
        )
        if created:
            profile.paid_message_balance += plan.bot_message_quota
            profile.updated_at = datetime.utcnow()
            profile.save()
        return payment
