from __future__ import annotations

from datetime import datetime

from app.db.models import Avatar, DialogMemory, DialogMessage, User


class MemoryService:
    @staticmethod
    def add_message(user: User, avatar: Avatar, role: str, content: str) -> DialogMessage:
        return DialogMessage.create(user=user, avatar=avatar, role=role, content=content)

    @staticmethod
    def get_or_create_memory(user: User, avatar: Avatar) -> DialogMemory:
        memory, _ = DialogMemory.get_or_create(user=user, avatar=avatar)
        return memory

    @staticmethod
    def recent_messages(user: User, avatar: Avatar, limit: int) -> list[DialogMessage]:
        query = (
            DialogMessage.select()
            .where((DialogMessage.user == user) & (DialogMessage.avatar == avatar))
            .order_by(DialogMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(list(query)))

    @staticmethod
    def messages_for_compaction(user: User, avatar: Avatar, after_message_id: int, batch_size: int) -> list[DialogMessage]:
        query = (
            DialogMessage.select()
            .where(
                (DialogMessage.user == user)
                & (DialogMessage.avatar == avatar)
                & (DialogMessage.id > after_message_id)
            )
            .order_by(DialogMessage.id)
            .limit(batch_size)
        )
        return list(query)

    @staticmethod
    def update_summary(memory: DialogMemory, summary: str, last_message_id: int) -> None:
        memory.rolling_summary = summary
        memory.last_compacted_message_id = last_message_id
        memory.updated_at = datetime.utcnow()
        memory.save()
