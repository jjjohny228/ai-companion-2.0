from __future__ import annotations

from app.db.models import Avatar, Gift, GiftPurchase, PremiumPhoto, User
from app.services.premium_photo_service import PremiumPhotoService


class GiftService:
    @staticmethod
    def list_active() -> list[Gift]:
        return list(Gift.select().where(Gift.is_active == True).order_by(Gift.stars_price, Gift.id))

    @staticmethod
    def get_active(gift_id: int) -> Gift | None:
        return Gift.get_or_none((Gift.id == gift_id) & (Gift.is_active == True))

    @staticmethod
    def build_payload(gift_id: int, avatar_id: int) -> str:
        return f"gift:{gift_id}:{avatar_id}"

    @staticmethod
    def parse_payload(payload: str) -> tuple[int, int] | None:
        parts = payload.split(":")
        if len(parts) != 3 or parts[0] != "gift":
            return None
        if not parts[1].isdigit() or not parts[2].isdigit():
            return None
        return int(parts[1]), int(parts[2])

    @staticmethod
    def register_purchase(
        user: User,
        avatar: Avatar,
        gift: Gift,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> GiftPurchase:
        rewarded_photo: PremiumPhoto | None = PremiumPhotoService.best_affordable_for_gift(avatar, user, gift.stars_price)
        purchase, _ = GiftPurchase.get_or_create(
            telegram_payment_charge_id=telegram_payment_charge_id,
            defaults={
                "user": user,
                "avatar": avatar,
                "gift": gift,
                "provider_payment_charge_id": provider_payment_charge_id,
                "stars_amount": gift.stars_price,
                "rewarded_premium_photo": rewarded_photo,
                "status": "paid",
            },
        )
        return purchase
