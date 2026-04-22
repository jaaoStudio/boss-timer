# app/services/room_service.py
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, joinedload

from app.database import models
from app.schemas import boss as boss_schemas


def generate_unique_room_id(db: Session, length: int = 10, max_attempts: int = 20) -> str:
    """生成唯一的房間ID"""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    for _ in range(max_attempts):
        room_id = ''.join(secrets.choice(chars) for _ in range(length))
        if not db.query(models.Room).filter(models.Room.room_id == room_id).first():
            return room_id
    raise Exception(f"Unable to generate unique room ID after {max_attempts} attempts")


def create_room(db: Session) -> models.Room:
    """創建新房間"""
    room_id = generate_unique_room_id(db, length=10)
    new_room = models.Room(room_id=room_id)
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    logging.info(f"Created new room: {room_id}")
    return new_room


def get_room_by_id(db: Session, room_id: str) -> Optional[models.Room]:
    """根據ID獲取房間"""
    return db.query(models.Room).filter(models.Room.room_id == room_id.upper(), models.Room.is_active == True).first()


def update_room_last_active(db: Session, room_id: str):
    """更新房間最後活躍時間"""
    room = get_room_by_id(db, room_id)
    if room:
        room.last_active = datetime.now(timezone.utc)
        db.commit()



def get_room_state(db: Session, room_id: str) -> dict:
    """獲取房間的完整初始狀態"""
    # 預先載入關聯數據以避免 N+1 查詢
    latest_records_query = db.query(models.BossRecord).options(
        joinedload(models.BossRecord.recorder),
        joinedload(models.BossRecord.boss_type)
    ).join(models.BossType).filter(
        models.BossRecord.room_id == room_id,
        models.BossRecord.is_archived == False  # 只獲取未歸檔的紀錄
    ).order_by(
        models.BossRecord.channel,
        models.BossType.name_en,
        models.BossRecord.recorded_at.desc()
    ).all()

    # 在 Python 中過濾出每個 (channel, boss_name) 的最新記錄
    unique_records: Dict[tuple, models.BossRecord] = {}
    for record in latest_records_query:
        key = (record.channel, record.boss_type.name_en)
        if key not in unique_records:
            unique_records[key] = record

    # 將 ORM 模型轉換為 Pydantic 模型
    boss_records_response = [
        boss_schemas.BossRecordResponse.model_validate(rec) for rec in unique_records.values()
    ]
    
    boss_types_response = [
        boss_schemas.BossTypeResponse.model_validate(bt) for bt in db.query(models.BossType).filter(
            (models.BossType.room_id == None) | (models.BossType.room_id == room_id)
        ).all()
    ]

    return {
        "type": "room_state",
        "boss_records": [rec.model_dump(mode='json') for rec in boss_records_response],
        "boss_types": [bt.model_dump(mode='json') for bt in boss_types_response]
    }
