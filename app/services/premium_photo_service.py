from __future__ import annotations

from app.db.models import Avatar, GiftPurchase, PremiumPhoto, PremiumPhotoPurchase, User


class PremiumPhotoService:
    @staticmethod
    def list_active_for_avatar(avatar: Avatar) -> list[PremiumPhoto]:
        return list(
            PremiumPhoto.select()
            .where((PremiumPhoto.avatar == avatar) & (PremiumPhoto.is_active == True))
            .order_by(PremiumPhoto.stars_price, PremiumPhoto.id)
        )

    @staticmethod
    def get_active(photo_id: int) -> PremiumPhoto | None:
        return PremiumPhoto.get_or_none((PremiumPhoto.id == photo_id) & (PremiumPhoto.is_active == True))

    @staticmethod
    def available_for_user(avatar: Avatar, user: User) -> list[PremiumPhoto]:
        purchased_ids = {
            item.premium_photo_id
            for item in PremiumPhotoPurchase.select(PremiumPhotoPurchase.premium_photo).where(
                (PremiumPhotoPurchase.user == user) & (PremiumPhotoPurchase.avatar == avatar)
            )
        }
        rewarded_ids = {
            item.rewarded_premium_photo_id
            for item in GiftPurchase.select(GiftPurchase.rewarded_premium_photo).where(
                (GiftPurchase.user == user)
                & (GiftPurchase.avatar == avatar)
                & (GiftPurchase.rewarded_premium_photo.is_null(False))
            )
        }
        consumed_ids = purchased_ids | rewarded_ids
        return [
            photo for photo in PremiumPhotoService.list_active_for_avatar(avatar)
            if photo.id not in consumed_ids
        ]

    @staticmethod
    def create(avatar: Avatar, photo_path: str, stars_price: int, description: str) -> PremiumPhoto:
        return PremiumPhoto.create(
            avatar=avatar,
            photo_path=photo_path,
            stars_price=stars_price,
            description=description,
        )

    @staticmethod
    def best_affordable_for_gift(avatar: Avatar, user: User, gift_stars_price: int) -> PremiumPhoto | None:
        available = PremiumPhotoService.available_for_user(avatar, user)
        affordable = [photo for photo in available if photo.stars_price <= gift_stars_price]
        if not affordable:
            return None
        affordable.sort(key=lambda item: (item.stars_price, item.id), reverse=True)
        return affordable[0]
