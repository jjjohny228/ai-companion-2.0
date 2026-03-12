from __future__ import annotations

from dataclasses import dataclass


LANGUAGES: dict[str, str] = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "uk": "🇺🇦 Українська",
}


@dataclass(frozen=True, slots=True)
class SubscriptionPlan:
    code: str
    title: str
    bot_message_quota: int
    stars_price: int


SUBSCRIPTION_PLANS: tuple[SubscriptionPlan, ...] = (
    SubscriptionPlan(code="plan_50", title="50 messages", bot_message_quota=50, stars_price=150),
    SubscriptionPlan(code="plan_100", title="100 messages", bot_message_quota=100, stars_price=280),
    SubscriptionPlan(code="plan_500", title="500 messages", bot_message_quota=500, stars_price=1200),
)


DEFAULT_LANGUAGE = "en"
