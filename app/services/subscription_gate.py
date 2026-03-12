from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from app.db.models import Channel, ChannelJoinRequest, User


class SubscriptionGateService:
    @staticmethod
    def active_channels() -> list[Channel]:
        return list(Channel.select().where(Channel.is_active == True).order_by(Channel.id))

    @staticmethod
    async def check_all(bot: Bot, user_id: int) -> bool:
        channels = SubscriptionGateService.active_channels()
        if not channels:
            return True
        user = User.get_or_none(User.telegram_id == user_id)
        for channel in channels:
            try:
                member = await bot.get_chat_member(chat_id=channel.telegram_channel_id, user_id=user_id)
            except TelegramBadRequest:
                member = None
            status = getattr(member, "status", None)
            if status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
                continue
            if channel.requires_join_request and user and SubscriptionGateService.has_pending_join_request(user, channel):
                continue
            return False
        return True

    @staticmethod
    def channel_links() -> list[str]:
        links = []
        for channel in SubscriptionGateService.active_channels():
            if channel.username_or_invite_link:
                links.append(channel.username_or_invite_link)
            else:
                links.append(channel.title)
        return links

    @staticmethod
    def register_join_request(user: User, channel: Channel) -> None:
        ChannelJoinRequest.insert(user=user, channel=channel, status="pending").on_conflict(
            conflict_target=[ChannelJoinRequest.user, ChannelJoinRequest.channel],
            preserve=[ChannelJoinRequest.status],
        ).execute()

    @staticmethod
    def has_pending_join_request(user: User, channel: Channel) -> bool:
        return ChannelJoinRequest.select().where(
            (ChannelJoinRequest.user == user)
            & (ChannelJoinRequest.channel == channel)
            & (ChannelJoinRequest.status == "pending")
        ).exists()
