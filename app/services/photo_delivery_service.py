from __future__ import annotations

import asyncio
import random
from pathlib import Path

from aiogram.types import FSInputFile, Message
from aiogram.types.input_paid_media_photo import InputPaidMediaPhoto
from langchain_xai import ChatXAI

from app.config import Settings
from app.db.models import Avatar
from app.services.dialog_service import DialogService


class PhotoDeliveryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = ChatXAI(
            model=settings.xai_model,
            api_key=settings.xai_api_key,
            temperature=0.9,
        )

    async def _generate_text(self, avatar: Avatar, language: str, mode: str) -> str:
        try:
            if mode == "gift":
                instruction = (
                    "Write one short in-character message thanking the user warmly for the gift "
                    "and saying to wait a little while you choose a very sweet photo."
                )
            else:
                instruction = (
                    "Write one short in-character message telling the user to wait a little while "
                    "because you are choosing the sweetest photo."
                )
            response = await self.llm.ainvoke(
                [
                    (
                        "system",
                        f"{DialogService.build_base_prompt(language, premium_available=True, lite_available=True)}\n"
                        f"Avatar description and personality:\n{avatar.system_prompt}",
                    ),
                    ("human", instruction),
                ]
            )
            return response.content if isinstance(response.content, str) else str(response.content)
        except Exception:
            if mode == "gift":
                return "Wait a little, I want to choose a very sweet photo for you. Thank you for the gift."
            return "Wait a little, I am choosing the sweetest photo for you."

    async def send_with_delay(self, message: Message, avatar: Avatar, language: str, photo_path: str, mode: str) -> None:
        teaser = await self._generate_text(avatar, language, mode)
        await message.answer(teaser)
        await asyncio.sleep(random.randint(20, 40))
        await message.answer_photo(FSInputFile(Path(photo_path)))

    async def send_paid_with_delay(
        self,
        message: Message,
        avatar: Avatar,
        language: str,
        photo_path: str,
        star_count: int,
        payload: str,
    ) -> None:
        teaser = await self._generate_text(avatar, language, "premium")
        await message.answer(teaser)
        await asyncio.sleep(random.randint(20, 40))
        await message.bot.send_paid_media(
            chat_id=message.chat.id,
            star_count=star_count,
            media=[InputPaidMediaPhoto(media=FSInputFile(Path(photo_path)))],
            payload=payload,
            protect_content=True,
        )
