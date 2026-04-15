# app/routers/bosses.py
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.database.models import BossType, BossRecord
from app.dependencies import limiter, verify_user_session, get_connection_manager
from app.schemas.boss import BossTypeResponse
from app.celery_app import celery_app
from app.websocket.manager import ConnectionManager

router = APIRouter(prefix="/boss", tags=["boss"])


@router.get("/boss-types", response_model=List[BossTypeResponse])
@limiter.limit("5/minute")
async def get_boss_types(request: Request, db: Session = Depends(get_db)):
    return db.query(BossType).all()

@router.delete("/room/{room_id}/records/{record_id}")
@limiter.limit("10/minute")
async def delete_boss_record(
    request: Request,
    room_id: str,
    record_id: int,
    db: Session = Depends(get_db),
    manager: ConnectionManager = Depends(get_connection_manager),
    _ = Depends(verify_user_session)
):
    """撤銷(作廢) BOSS 紀錄，並撤銷已註冊的 Celery 預警推播。"""
    record = db.query(BossRecord).filter(
        BossRecord.id == record_id,
        BossRecord.room_id == room_id,
        BossRecord.is_archived == False
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # 1. 撤銷 Celery tasks
    if record.celery_task_ids:
        celery_ids = record.celery_task_ids
        for key, task_id in celery_ids.items():
            if task_id:
                celery_app.control.revoke(task_id, terminate=False)

    # 2. Soft delete
    record.is_archived = True
    db.commit()

    # 3. WebSocket Broadcast
    await manager.broadcast_to_room(
        room_id=room_id,
        message={
            "type": "record_deleted",
            "data": {"record_id": record_id, "room_id": room_id}
        }
    )

    return {"message": "Record archived successfully"}


