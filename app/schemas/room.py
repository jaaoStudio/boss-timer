# app/schemas/room.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class RoomCreate(BaseModel):
    room_id: str= Field(..., max_length=10)


class RoomResponse(BaseModel):
    room_id: str= Field(..., max_length=10)
    created_at: datetime
    last_active: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomExists(BaseModel):
    exists: bool
    room_id: str= Field(..., max_length=10)
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None