# app/routers/rooms.py
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.dependencies import limiter, verify_user_session
from app.services.room_service import create_room as room_service_create_room, get_room_by_id
from app.schemas.room import RoomResponse, RoomExists, RoomSettingsUpdate
import logging

router = APIRouter(prefix="/room", tags=["rooms"])


@router.post("/", response_model=RoomResponse)
@limiter.limit("15/minute")
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
@limiter.limit("15/minute")
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
                discord_webhook_url=room.discord_webhook_url,
                discord_webhook_enabled=room.discord_webhook_enabled or False,
                webhook_notify_events=room.webhook_notify_events or ["killed", "alive", "not_found"],
                webhook_alert_type=room.webhook_alert_type or "none"
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

@router.patch("/{room_id}/settings", response_model=RoomResponse)
@limiter.limit("30/minute")
async def update_room_settings(
        request: Request,
        settings_data: RoomSettingsUpdate,
        room_id: str = Path(..., min_length=10, max_length=10),
        db: Session = Depends(get_db),
        _ = Depends(verify_user_session)
):
    """更新房間設定 (Webhook 等)"""
    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
        
    try:
        update_data = settings_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(room, key, value)
        
        db.commit()
        db.refresh(room)
        return RoomResponse.model_validate(room)
    except Exception as e:
        db.rollback()
        logging.error(f"Update room settings error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update room settings")