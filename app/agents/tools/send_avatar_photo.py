from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.db.models import Avatar, User
from app.services.photo_offer_service import PhotoOfferService


class SendAvatarPhotoInput(BaseModel):
    reason: str = Field(description="Why the agent wants to send a photo.")


@dataclass(slots=True)
class PendingPhoto:
    path: Path | None = None


def build_send_avatar_photo_tool(assets_dir: Path, user: User, avatar: Avatar, pending_photo: PendingPhoto) -> StructuredTool:
    def _send_avatar_photo(reason: str) -> str:
        photo = PhotoOfferService.pick_random_photo(assets_dir, user, avatar)
        if not photo:
            return "No new photo is available, so do not offer or promise one."
        pending_photo.path = photo
        return f"Photo prepared for sending. Mention it naturally. Reason noted: {reason}"

    return StructuredTool.from_function(
        func=_send_avatar_photo,
        name="send_avatar_photo",
        description="Use when you want to send one new avatar photo and only when it feels appropriate.",
        args_schema=SendAvatarPhotoInput,
    )
