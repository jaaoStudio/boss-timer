# app/schemas/boss.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from .auth import User  # 引入 User schema


class BossRecordCreate(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=10, description="房間ID")
    channel: int = Field(..., ge=1, le=99999, description="頻道號碼")
    boss_type_id: int = Field(..., description="Boss類型ID")
    status: str = Field(..., min_length=1, max_length=20, description="狀態")
    recorder_id: Optional[int] = None # 允許傳入記錄者ID
    recorder_info: Optional[Dict[str, Any]] = None # 允許傳入匿名記錄者資訊


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
    recorder: Optional[User] = None # 顯示記錄的使用者資訊
    recorder_info: Optional[Dict[str, Any]] = None # 顯示匿名記錄者資訊
    current_status: str
    boss_type: BossTypeResponse

    model_config = ConfigDict(from_attributes=True)