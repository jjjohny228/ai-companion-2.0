from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.db.models import Avatar, PremiumPhoto, User
from app.services.photo_offer_service import PhotoOfferService


class ToolReasonInput(BaseModel):
    reason: str = Field(description="Why the agent wants to send this photo.")


@dataclass(slots=True)
class PendingPhotoActions:
    lite_path: Path | None = None
    premium_photo: PremiumPhoto | None = None


def build_send_lite_photo_tool(assets_dir: Path, user: User, avatar: Avatar, pending: PendingPhotoActions) -> StructuredTool:
    def _send_lite_photo(reason: str) -> str:
        photo = PhotoOfferService.pick_random_lite_photo(assets_dir, user, avatar)
        if not photo:
            return "No new lite photo is available, so do not mention or promise one."
        pending.lite_path = photo
        return f"Lite photo prepared. Mention it naturally. Reason noted: {reason}"

    return StructuredTool.from_function(
        func=_send_lite_photo,
        name="send_lite_photo",
        description="Use when you want to send one free lite photo immediately and naturally.",
        args_schema=ToolReasonInput,
    )


def build_send_premium_photo_tool(user: User, avatar: Avatar, pending: PendingPhotoActions) -> StructuredTool:
    def _send_premium_photo(reason: str) -> str:
        photo = PhotoOfferService.pick_random_premium_photo(user, avatar)
        if not photo:
            return "No unseen premium photo is available, so do not mention or offer one."
        pending.premium_photo = photo
        return (
            f"Premium photo prepared as paid blurred media for {photo.stars_price} Stars. "
            f"Mention it naturally. Reason noted: {reason}"
        )

    return StructuredTool.from_function(
        func=_send_premium_photo,
        name="send_premium_photo",
        description="Use when you want to offer one unseen premium photo as blurred paid media in Telegram Stars.",
        args_schema=ToolReasonInput,
    )
