# app/routers/auth.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Set, Any, Coroutine, Type
from app.config import settings
from app.database.database import get_db
from app.database.models import BossRecord, BossType
from app.services.room_service import RoomService
from app.services.boss_service import BossService
from app.schemas.boss import BossTypeResponse, BossRecordCreate
from app.utils.jwt_helper import get_current_user_id
import logging

router = APIRouter(prefix="/boss", tags=["boss"])


@router.post("/record-boss")
async def record_boss(
        record: BossRecordCreate,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    """記錄 BOSS 狀態"""
    try:
        # 驗證房間和 BOSS 類型
        room = await BossService._validate_room_exists(db, record.room_id)
        boss_type = await BossService._validate_boss_type_exists(db, record.boss_name)

        # 計算重生時間
        respawn_times = await BossService._calculate_respawn_times(db, record, boss_type)

        # 創建 BOSS 記錄
        boss_record = await BossService._create_boss_record(db, record, respawn_times, user_id)

        # 更新房間最後活躍時間
        await RoomService._update_room_last_active(db, room)

        # 廣播更新
        await BossService._broadcast_boss_update(record.room_id, boss_record, boss_type)

        # 返回響應
        return BossService._create_success_response(boss_record, boss_type)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Record boss error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record boss status {e}")


@router.get("/boss-types", response_model=List[BossTypeResponse])
async def get_boss_types(db: Session = Depends(get_db)):
    return db.query(BossType).all()

def serialize_boss_record(boss_record: BossRecord, boss_type: BossType) -> dict:
    record_dict = boss_record.__dict__.copy()
    record_dict.update({
        "min_respawn_minutes": boss_type.min_respawn_minutes,
        "max_respawn_minutes": boss_type.max_respawn_minutes,
        "current_status": BossService.get_current_status(boss_record, boss_type),
        "recorded_at": boss_record.recorded_at.isoformat(),
        "respawn_min_time": boss_record.respawn_min_time.isoformat() if boss_record.respawn_min_time else None,
        "respawn_max_time": boss_record.respawn_max_time.isoformat() if boss_record.respawn_max_time else None,
    })
    return record_dict