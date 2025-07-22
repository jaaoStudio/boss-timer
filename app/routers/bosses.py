# app/routers/auth.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Set, Any, Coroutine, Type
from app.config import settings
from app.database.database import get_db
from app.database.models import BossRecord, BossType
from app.services.room_service import update_room_last_active
from app.services.boss_service import BossService
from app.schemas.boss import BossTypeResponse, BossRecordCreate, BossRecordResponse
from app.utils.jwt_helper import get_current_user_id, get_optional_current_user_id
import logging

router = APIRouter(prefix="/boss", tags=["boss"])


@router.post("/record-boss")
async def record_boss(
        record: BossRecordCreate,
        db: Session = Depends(get_db),
        user_id: Optional[str] = Depends(get_optional_current_user_id)
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
        update_room_last_active(db, record.room_id)

        # The broadcast is now handled via WebSocket messages, so we remove it from the HTTP endpoint.
        # await BossService._broadcast_boss_update(db=db, room_id=record.room_id, boss_record_id=boss_record.id)

        # 返回響應
        return BossRecordResponse.model_validate(boss_record)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Record boss error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record boss status {e}")


@router.get("/boss-types", response_model=List[BossTypeResponse])
async def get_boss_types(db: Session = Depends(get_db)):
    return db.query(BossType).all()

