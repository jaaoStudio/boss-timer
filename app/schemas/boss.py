# app/schemas/boss.py
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from .auth import PublicUser, RecorderInfo


class BossStatus(str, Enum):
    alive = "alive"
    killed = "killed"
    not_found = "not_found"


class BossRecordCreate(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=10, description="房間ID")
    channel: int = Field(..., ge=1, le=99999, description="頻道號碼")
    boss_type_id: int = Field(..., description="Boss類型ID")
    status: BossStatus = Field(..., description="狀態")
    recorder_info: Optional[RecorderInfo] = None


class BossTypeResponse(BaseModel):
    id: int
    name_en: str
    name_zh: str
    min_respawn_minutes: int
    max_respawn_minutes: int
    description: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class BossRecordResponse(BaseModel):
    id: int
    room_id: str
    channel: int
    boss_type_id: int
    status: str
    recorded_at: datetime
    respawn_min_time: Optional[datetime]
    respawn_max_time: Optional[datetime]
    recorder: Optional[PublicUser] = None
    recorder_info: Optional[RecorderInfo] = None
    current_status: str
    boss_type: BossTypeResponse

    model_config = ConfigDict(from_attributes=True)