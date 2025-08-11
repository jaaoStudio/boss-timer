# app/routers/rooms.py
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.dependencies import limiter, verify_user_session
from app.services.room_service import create_room as room_service_create_room, get_room_by_id
from app.services.boss_service import BossService
from app.schemas.room import RoomResponse, RoomExists
from app.database.models import BossRecord, BossType
from app.utils.jwt_helper import get_current_user_id, get_optional_current_user_id
from typing import Optional
import logging

router = APIRouter(prefix="/room", tags=["rooms"])


@router.post("/", response_model=RoomResponse)
@limiter.limit("5/minute")
async def create_room(
        request: Request,
        db: Session = Depends(get_db),
        _ = Depends(verify_user_session)
):
    """創建新房間"""
    try:
        room = room_service_create_room(db)
        return RoomResponse.model_validate(room)
    except Exception as e:
        logging.error(f"Create room error: {e}")
        if "Unable to generate unique room ID" in str(e):
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        raise HTTPException(status_code=500, detail="Failed to create room")


@router.get("/{room_id}/exists", response_model=RoomExists)
@limiter.limit("5/minute")
async def check_room_exists(request: Request, room_id: str= Path(..., min_length=10, max_length=10, description="房間 ID，固定 10 個字元"),
                            db: Session = Depends(get_db)):
    """檢查房間是否存在"""
    try:
        room = get_room_by_id(db, room_id)

        if room:
            return RoomExists(
                exists=True,
                room_id=room.room_id,
                created_at=room.created_at,
                last_active=room.last_active,
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=RoomExists(exists=False, room_id=room_id.upper()).model_dump()
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Check room exists error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check room existence")


@router.get("/{room_id}/history")
async def get_room_history(
        room_id: str,
        boss_name: Optional[str] = None,
        limit: int = 50,
        db: Session = Depends(get_db)
):
    try:
        query = db.query(BossRecord, BossType).join(BossType).filter(BossRecord.room_id == room_id)

        if boss_name:
            query = query.filter(BossRecord.boss_name == boss_name)

        results = query.order_by(BossRecord.recorded_at.desc()).limit(limit).all()

        records = []
        for boss_record, boss_type in results:
            records.append(BossService.serialize_boss_record(boss_record, boss_type))

        return records

    except Exception as e:
        logging.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history")