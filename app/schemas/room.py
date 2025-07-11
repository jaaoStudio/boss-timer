# app/schemas/room.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RoomCreate(BaseModel):
    room_id: str


class RoomResponse(BaseModel):
    room_id: str
    created_at: datetime
    last_active: datetime

    class Config:
        from_attributes = True


class RoomExists(BaseModel):
    exists: bool
    room_id: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
