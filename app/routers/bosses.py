# app/routers/bosses.py
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.database.models import BossType, BossRecord
from app.dependencies import limiter, verify_user_session, get_connection_manager
from app.schemas.boss import BossTypeResponse, CustomBossTypeCreate
from app.celery_app import celery_app
from app.websocket.manager import ConnectionManager

router = APIRouter(prefix="/boss", tags=["boss"])


@router.get("/boss-types", response_model=List[BossTypeResponse])
@limiter.limit("15/minute")
async def get_boss_types(request: Request, db: Session = Depends(get_db)):
    """取得全域 Boss 種類（不含房間自訂）"""
    return db.query(BossType).filter(BossType.room_id == None).all()


@router.post("/room/{room_id}/boss-types", response_model=BossTypeResponse)
@limiter.limit("30/minute")
async def create_custom_boss_type(
    request: Request,
    room_id: str,
    payload: CustomBossTypeCreate,
    db: Session = Depends(get_db),
    _ = Depends(verify_user_session)
):
    """新增房間自訂 Boss"""
    from app.services.room_service import get_room_by_id
    if not get_room_by_id(db, room_id):
        raise HTTPException(status_code=404, detail="Room not found")

    custom = BossType(
        room_id=room_id,
        name_en=payload.name,
        name_zh=payload.name,
        min_respawn_minutes=payload.min_respawn_minutes,
        max_respawn_minutes=payload.max_respawn_minutes,
    )
    db.add(custom)
    db.commit()
    db.refresh(custom)
    return custom


@router.delete("/room/{room_id}/boss-types/{boss_type_id}")
@limiter.limit("30/minute")
async def delete_custom_boss_type(
    request: Request,
    room_id: str,
    boss_type_id: int,
    db: Session = Depends(get_db),
    _ = Depends(verify_user_session)
):
    """刪除房間自訂 Boss（只能刪自己房間的）"""
    boss = db.query(BossType).filter(
        BossType.id == boss_type_id,
        BossType.room_id == room_id
    ).first()

    if not boss:
        raise HTTPException(status_code=404, detail="Custom boss type not found")

    # 撤銷所有關聯記錄的 Celery 預警任務
    related_records = db.query(BossRecord).filter(
        BossRecord.boss_type_id == boss_type_id,
        BossRecord.is_archived == False
    ).all()
    for record in related_records:
        if record.celery_task_ids:
            for task_id in record.celery_task_ids.values():
                if task_id:
                    celery_app.control.revoke(task_id, terminate=False)

    # FK ondelete="CASCADE" 會自動刪除關聯的 BossRecord
    db.delete(boss)
    db.commit()
    return {"message": "Custom boss type deleted"}

@router.delete("/room/{room_id}/records/{record_id}")
@limiter.limit("15/minute")
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


