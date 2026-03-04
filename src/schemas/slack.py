from pydantic import BaseModel
from typing import Any


class SlashCommandPayload(BaseModel):
    token: str | None = None
    command: str
    text: str
    response_url: str
    channel_id: str
    channel_name: str
    user_id: str
    user_name: str


class InteractivityPayload(BaseModel):
    type: str
    actions: list[dict[str, Any]]
    channel: dict[str, Any]
    user: dict[str, Any]
    response_url: str | None = None