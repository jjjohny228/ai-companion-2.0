from __future__ import annotations

import base64
from io import BytesIO

from aiohttp import ClientSession
from aiogram import Bot
from aiogram.types import PhotoSize

from app.config import Settings


class ImageAnalysisService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def describe_telegram_photo(self, bot: Bot, photo: PhotoSize, user_caption: str, language: str) -> str:
        file = await bot.get_file(photo.file_id)
        buffer = BytesIO()
        await bot.download_file(file.file_path, destination=buffer)
        image_bytes = buffer.getvalue()
        if not image_bytes:
            return self._fallback_text(user_caption)

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": self.settings.xai_vision_model,
            "store": False,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{encoded}",
                            "detail": "high",
                        },
                        {
                            "type": "input_text",
                            "text": (
                                "Describe this user-uploaded image for a Telegram chat reply. "
                                f"Write in {language}. Focus on visible details, mood, clothing, pose, objects, and likely intent. "
                                "Keep it concise and factual. If the user also added a caption, use it as extra context.\n"
                                f"User caption: {user_caption or 'none'}"
                            ),
                        },
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.settings.xai_api_key}",
            "Content-Type": "application/json",
        }
        async with ClientSession() as session:
            async with session.post("https://api.x.ai/v1/responses", headers=headers, json=payload, timeout=120) as response:
                if response.status >= 400:
                    return self._fallback_text(user_caption)
                data = await response.json()
        return self._extract_text(data) or self._fallback_text(user_caption)

    @staticmethod
    def _extract_text(data: dict) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = data.get("output", [])
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text", "")
                    if text.strip():
                        return text.strip()
        return ""

    @staticmethod
    def _fallback_text(user_caption: str) -> str:
        if user_caption.strip():
            return f"The user sent a photo with caption: {user_caption.strip()}"
        return "The user sent a photo."
