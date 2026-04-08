from __future__ import annotations

from pathlib import Path

from aiogram.types import FSInputFile, Message
from aiogram.types.input_paid_media_photo import InputPaidMediaPhoto

from app.config import Settings


class PhotoDeliveryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_with_delay(self, message: Message, avatar, language: str, photo_path: str, mode: str) -> None:
        await message.answer_photo(FSInputFile(Path(photo_path)))

    async def send_paid_with_delay(
        self,
        message: Message,
        avatar,
        language: str,
        photo_path: str,
        star_count: int,
        payload: str,
        send_teaser: bool = True,
    ) -> None:
        await message.bot.send_paid_media(
            chat_id=message.chat.id,
            star_count=star_count,
            media=[InputPaidMediaPhoto(media=FSInputFile(Path(photo_path)))],
            payload=payload,
            protect_content=True,
        )
