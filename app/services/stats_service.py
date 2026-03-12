from __future__ import annotations

from datetime import datetime, timedelta

from peewee import fn

from app.db.models import Avatar, DialogMessage, Payment, User


class StatsService:
    @staticmethod
    def collect(period: str) -> dict[str, int]:
        now = datetime.utcnow()
        start = None
        if period == "day":
            start = now - timedelta(days=1)
        elif period == "month":
            start = now - timedelta(days=30)

        user_query = User.select()
        message_query = DialogMessage.select()
        payment_query = Payment.select().where(Payment.status == "paid")

        if start:
            user_query = user_query.where(User.created_at >= start)
            message_query = message_query.where(DialogMessage.created_at >= start)
            payment_query = payment_query.where(Payment.created_at >= start)

        top_avatar = (
            Avatar.select(Avatar.display_name, fn.COUNT(DialogMessage.id).alias("message_count"))
            .join(DialogMessage, on=(DialogMessage.avatar == Avatar.id))
            .group_by(Avatar.id)
            .order_by(fn.COUNT(DialogMessage.id).desc())
            .first()
        )

        return {
            "users": user_query.count(),
            "messages": message_query.count(),
            "payments": payment_query.count(),
            "stars": sum(item.stars_amount for item in payment_query),
            "top_avatar_messages": getattr(top_avatar, "message_count", 0) or 0,
        }
