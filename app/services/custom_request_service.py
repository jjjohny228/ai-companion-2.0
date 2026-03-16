from __future__ import annotations

from datetime import datetime

from app.db.models import Avatar, CustomContentDelivery, CustomContentRequest, User


class CustomRequestService:
    PRICE_MAP = {
        "photo": 2000,
        "video": 4000,
    }

    @staticmethod
    def create(user: User, avatar: Avatar, media_type: str, description: str) -> CustomContentRequest:
        return CustomContentRequest.create(
            user=user,
            avatar=avatar,
            media_type=media_type,
            description=description,
            stars_price=CustomRequestService.PRICE_MAP[media_type],
            status="pending",
        )

    @staticmethod
    def mark_delivered(
        user: User,
        media_type: str,
        stars_price: int,
        caption_text: str = "",
        description: str = "",
    ) -> CustomContentDelivery:
        request = (
            CustomContentRequest.select()
            .where((CustomContentRequest.user == user) & (CustomContentRequest.status == "pending"))
            .order_by(CustomContentRequest.id.desc())
            .first()
        )
        avatar = request.avatar if request else None
        final_description = description or (request.description if request else "")
        if request:
            request.status = "delivered"
            request.fulfilled_at = datetime.utcnow()
            request.save()
        delivery = CustomContentDelivery.create(
            user=user,
            avatar=avatar,
            request=request,
            media_type=media_type,
            description=final_description,
            caption_text=caption_text,
            stars_price=stars_price,
        )
        if avatar:
            from app.services.memory_service import MemoryService

            MemoryService.add_message(
                user,
                avatar,
                "assistant",
                (
                    "[Delivery note] The latest custom "
                    f"{media_type} has already been delivered to the user. "
                    "Do not say it is still being prepared. "
                    "If it comes up in chat, react as if the user has already received it and ask how they liked it."
                ),
            )
        return delivery

    @staticmethod
    def latest_delivery_context(user: User, avatar: Avatar) -> str:
        delivery = (
            CustomContentDelivery.select()
            .where(
                (CustomContentDelivery.user == user)
                & (CustomContentDelivery.avatar == avatar)
            )
            .order_by(CustomContentDelivery.id.desc())
            .first()
        )
        if not delivery:
            return ""
        return (
            "Latest delivered custom content:\n"
            f"- type: {delivery.media_type}\n"
            f"- description: {delivery.description or 'not specified'}\n"
            f"- stars: {delivery.stars_price}\n"
            f"- delivered_at: {delivery.created_at.isoformat()}\n"
            "- This custom content is already delivered. Do not say it is still being prepared or that it is now ready.\n"
            "- If the user talks about it, respond like they already received it and ask how they liked it.\n"
        )
