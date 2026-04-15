# app/schemas/room.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


class RoomCreate(BaseModel):
    room_id: str= Field(..., max_length=10)


class RoomResponse(BaseModel):
    room_id: str= Field(..., max_length=10)
    created_at: datetime
    last_active: datetime
    discord_webhook_url: Optional[str] = None
    discord_webhook_enabled: bool = False
    webhook_notify_events: Optional[List[str]] = Field(default_factory=lambda: ["killed", "alive", "not_found"])
    webhook_alert_type: Optional[str] = "none"

    model_config = ConfigDict(from_attributes=True)

class RoomSettingsUpdate(BaseModel):
    discord_webhook_url: Optional[str] = Field(None, max_length=1000, pattern=r"^(https://discord\.com/api/webhooks/|https://discordapp\.com/api/webhooks/).+")
    discord_webhook_enabled: Optional[bool] = False
    webhook_notify_events: Optional[List[str]] = None
    webhook_alert_type: Optional[str] = Field("none", pattern="^(min|max|both|none)$")



class RoomExists(BaseModel):
    exists: bool
    room_id: str= Field(..., max_length=10)
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    discord_webhook_url: Optional[str] = None
    discord_webhook_enabled: bool = False
    webhook_notify_events: Optional[List[str]] = Field(default_factory=lambda: ["killed", "alive", "not_found"])
    webhook_alert_type: Optional[str] = "none"