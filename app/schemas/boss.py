# app/schemas/boss.py
from pydantic import BaseModel, Field
from typing import Optional

class BossRecordCreate(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=10, description="房間ID")
    channel: int = Field(..., ge=1, le=99999, description="頻道號碼")
    boss_name: str = Field(..., min_length=1, max_length=100, description="Boss名稱")
    status: str = Field(..., min_length=1, max_length=20, description="狀態")

class BossRecordResponse(BaseModel):
    id: int
    room_id: str
    channel: int
    boss_name: str
    status: str
    recorded_at: str
    respawn_min_time: Optional[str]
    respawn_max_time: Optional[str]
    current_status: str
    min_respawn_minutes: int
    max_respawn_minutes: int

class BossTypeResponse(BaseModel):
    boss_name: str
    min_respawn_minutes: int
    max_respawn_minutes: int
    description: Optional[str]