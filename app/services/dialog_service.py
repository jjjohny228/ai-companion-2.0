from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_xai import ChatXAI

from app.agents.tools.send_avatar_photo import (
    PendingPhotoActions,
    build_send_lite_photo_tool,
    build_send_premium_photo_tool,
)
from app.config import Settings
from app.db.models import Avatar, User, UserProfile
from app.services.memory_service import MemoryService
from app.services.photo_offer_service import PhotoOfferService


logger = logging.getLogger(__name__)


class DialogService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = ChatXAI(
            model=settings.xai_model,
            api_key=settings.xai_api_key,
            temperature=0.8,
        )

    def build_system_prompt(self, avatar: Avatar, language: str, premium_available: bool, lite_available: bool) -> str:
        premium_clause = (
            "You may offer a premium photo only if it feels natural."
            if premium_available
            else "Do not mention premium photos because no unseen premium photo is available."
        )
        lite_clause = (
            "You may send a free lite photo if it feels natural."
            if lite_available
            else "Do not mention free photos because no unseen lite photo is available."
        )
        return (
            f"{avatar.system_prompt}\n"
            f"Use only {language} language.\n"
            f"{premium_clause}\n"
            f"{lite_clause}\n"
            "If you offer a premium photo, present it as a blurred locked photo that can be opened with Stars. "
            "If you send a lite photo, present it as a free normal photo. "
            "Do not claim that a photo was already sent until the tool is used. "
            "Keep replies concise, engaging, and in character."
        )

    async def answer(self, user: User, profile: UserProfile, avatar: Avatar, incoming_text: str):
        premium_available = PhotoOfferService.has_available_photo(self.settings.assets_dir, user, avatar)
        memory = MemoryService.get_or_create_memory(user, avatar)
        recent_messages = MemoryService.recent_messages(user, avatar, self.settings.summary_window_size)
        pending = PendingPhotoActions()
        tools = [
            build_send_lite_photo_tool(self.settings.assets_dir, user, avatar, pending),
            build_send_premium_photo_tool(user, avatar, pending),
        ]
        llm = self.llm.bind_tools(tools)

        lite_available = bool(PhotoOfferService.list_available_photos(self.settings.assets_dir, user, avatar, bucket="photos"))
        messages = [SystemMessage(content=self.build_system_prompt(avatar, profile.language, premium_available, lite_available))]
        if memory.rolling_summary:
            messages.append(SystemMessage(content=f"Conversation summary: {memory.rolling_summary}"))
        for message in recent_messages:
            if message.role == "user":
                messages.append(HumanMessage(content=message.content))
            else:
                messages.append(AIMessage(content=message.content))
        messages.append(HumanMessage(content=incoming_text))

        MemoryService.add_message(user, avatar, "user", incoming_text)
        response = await llm.ainvoke(messages)
        if getattr(response, "tool_calls", None):
            messages.append(response)
            tool_index = {tool.name: tool for tool in tools}
            for tool_call in response.tool_calls:
                tool = tool_index.get(tool_call["name"])
                if not tool:
                    continue
                result = tool.invoke(tool_call["args"])
                messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
            response = await llm.ainvoke(messages)
        text = response.content if isinstance(response.content, str) else str(response.content)
        MemoryService.add_message(user, avatar, "assistant", text)
        await self.compact_if_needed(user, avatar)
        return text, pending

    async def compact_if_needed(self, user: User, avatar: Avatar) -> None:
        memory = MemoryService.get_or_create_memory(user, avatar)
        batch = MemoryService.messages_for_compaction(
            user=user,
            avatar=avatar,
            after_message_id=memory.last_compacted_message_id,
            batch_size=self.settings.summary_batch_size,
        )
        if len(batch) < self.settings.summary_batch_size:
            return
        source_lines = [f"{item.role}: {item.content}" for item in batch]
        prompt = [
            SystemMessage(
                content=(
                    "Summarize the conversation history for future dialogue continuity. "
                    "Keep important preferences, promises, emotional context, and open loops."
                )
            ),
            HumanMessage(
                content=(
                    f"Previous summary:\n{memory.rolling_summary or 'No summary yet.'}\n\n"
                    f"New messages:\n" + "\n".join(source_lines)
                )
            ),
        ]
        response = await self.llm.ainvoke(prompt)
        summary = response.content if isinstance(response.content, str) else str(response.content)
        MemoryService.update_summary(memory, summary, batch[-1].id)
        logger.info("dialog_summary_updated user_id=%s avatar_id=%s", user.id, avatar.id)
