# app/services/room_service.py
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import or_, and_
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



ROOM_STATE_WINDOW_DAYS = 2


def get_room_state(db: Session, room_id: str) -> dict:
    """獲取房間的完整初始狀態"""
    # 由 DB 以 DISTINCT ON 取出每個 (channel, boss_type_id) 最新紀錄，
    # 結果筆數被 channels × boss_types 綁定，不隨總紀錄數增長。
    # 並用時間窗過濾掉太舊的紀錄，讓頻道總覽只反映近期活躍頻道。
    cutoff = datetime.now(timezone.utc) - timedelta(days=ROOM_STATE_WINDOW_DAYS)

    room = get_room_by_id(db, room_id)
    last_cleared_at: dict = (room.last_cleared_at or {}) if room else {}

    # 建立 per-boss-type 清除時間過濾條件
    # 若某 boss_type_id 有 last_cleared_at，則該 boss 的紀錄必須在清除時間之後
    cleared_boss_ids = [int(k) for k in last_cleared_at.keys()]
    cleared_conditions = [
        and_(
            models.BossRecord.boss_type_id == int(bt_id_str),
            models.BossRecord.recorded_at >= datetime.fromisoformat(cleared_at_str),
        )
        for bt_id_str, cleared_at_str in last_cleared_at.items()
    ]

    latest_records = db.query(models.BossRecord).options(
        joinedload(models.BossRecord.recorder),
        joinedload(models.BossRecord.boss_type),
    ).filter(
        models.BossRecord.room_id == room_id,
        models.BossRecord.is_archived == False,
        models.BossRecord.recorded_at >= cutoff,
        or_(
            ~models.BossRecord.boss_type_id.in_(cleared_boss_ids),
            *cleared_conditions,
        ) if cleared_boss_ids else True,
    ).order_by(
        models.BossRecord.channel,
        models.BossRecord.boss_type_id,
        models.BossRecord.recorded_at.desc(),
    ).distinct(
        models.BossRecord.channel,
        models.BossRecord.boss_type_id,
    ).all()

    boss_records_response = [
        boss_schemas.BossRecordResponse.model_validate(rec) for rec in latest_records
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
