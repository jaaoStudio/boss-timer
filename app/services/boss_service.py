from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Response
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from app.database.models import Room, RoomUser, BossRecord, BossType
from app.schemas.boss import BossRecordResponse, BossTypeResponse, BossRecordCreate

from app.dependencies import get_current_user_from_ws, ConnectionManager, get_connection_manager

class BossService:
    @staticmethod
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

    @staticmethod
    def get_current_status(boss_record: BossRecord, boss_type: BossType) -> str:
        now = datetime.now(timezone.utc)

        if boss_record.status == "killed":
            if boss_record.respawn_max_time and now >= boss_record.respawn_max_time:
                return "alive"  # Or some other status indicating it should have respawned
            if boss_record.respawn_min_time and now >= boss_record.respawn_min_time:
                return "may_respawn"
            return "respawning"

        return boss_record.status

    @staticmethod
    async def _validate_room_exists(db: Session, room_id: str) -> Room:
        """驗證房間是否存在"""
        room = db.query(Room).filter(Room.room_id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail=f"房間 {room_id} 不存在")
        return room  # type: ignore

    @staticmethod
    async def _validate_boss_type_exists(db: Session, boss_name: str) -> BossType:
        """驗證 BOSS 類型是否存在"""
        boss_type = db.query(BossType).filter(BossType.boss_name == boss_name).first()
        if not boss_type:
            raise HTTPException(status_code=400, detail="Invalid boss type")
        return boss_type  # type: ignore

    @staticmethod
    async def _calculate_respawn_times(
            db: Session,
            record: BossRecordCreate,
            boss_type: BossType
    ) -> dict:
        """計算 BOSS 重生時間"""
        now = datetime.now(timezone.utc)

        if record.status == "killed":
            base_time = now
        elif record.status == "respawning":
            base_time = await BossService._get_last_killed_time(db, record) or now
        else:
            # 其他狀態不需要重生時間
            return {
                "respawn_min_time": None,
                "respawn_max_time": None,
                "base_time": now
            }

        return {
            "respawn_min_time": base_time + timedelta(minutes=boss_type.min_respawn_minutes),
            "respawn_max_time": base_time + timedelta(minutes=boss_type.max_respawn_minutes),
            "base_time": now
        }

    @staticmethod
    async def _create_boss_record(
            db: Session,
            record: BossRecordCreate,
            respawn_times: dict,
            user_id: str
    ) -> BossRecord:
        """創建 BOSS 記錄"""
        boss_record = BossRecord(
            room_id=record.room_id,
            channel=record.channel,
            boss_name=record.boss_name,
            status=record.status,
            recorded_at=respawn_times["base_time"],
            respawn_min_time=respawn_times["respawn_min_time"],
            respawn_max_time=respawn_times["respawn_max_time"],
            recorder_info={"user_id": user_id}
        )

        db.add(boss_record)
        db.commit()
        db.refresh(boss_record)

        return boss_record

    @staticmethod
    async def _broadcast_boss_update(room_id: str, boss_record: BossRecord, boss_type: BossType):
        """廣播 BOSS 更新"""
        boss_record_response = BossService._create_boss_record_response(boss_record, boss_type)

        await get_connection_manager().broadcast_to_room(room_id=room_id, message={
            "type": "boss_update",
            "data": boss_record_response.__dict__
        })

        logging.info(f"Broadcasted boss_update for room {room_id}: {boss_record_response}")

    @staticmethod
    def _create_success_response(boss_record: BossRecord, boss_type: BossType) -> dict:
        """創建成功響應"""
        boss_record_response = BossService._create_boss_record_response(boss_record, boss_type)
        return {"success": True, "data": boss_record_response}

    @staticmethod
    def _create_boss_record_response(boss_record: BossRecord, boss_type: BossType) -> BossRecordResponse:
        """創建 BossRecordResponse 對象"""
        return BossRecordResponse(
            id=boss_record.id,
            room_id=boss_record.room_id,
            channel=boss_record.channel,
            boss_name=boss_record.boss_name,
            status=boss_record.status,
            recorded_at=boss_record.recorded_at,
            respawn_min_time=boss_record.respawn_min_time.isoformat() if boss_record.respawn_min_time else None,
            respawn_max_time=boss_record.respawn_max_time.isoformat() if boss_record.respawn_max_time else None,
            current_status=BossService.get_current_status(boss_record, boss_type)
        )

    @staticmethod
    async def _get_last_killed_time(db: Session, record: BossRecordCreate) -> Optional[datetime]:
        """獲取最後一次被殺死的時間"""
        last_killed_record = db.query(BossRecord).filter(
            BossRecord.room_id == record.room_id,
            BossRecord.channel == record.channel,
            BossRecord.boss_name == record.boss_name,
            BossRecord.status == "killed"
        ).order_by(BossRecord.recorded_at.desc()).first()

        return last_killed_record.recorded_at if last_killed_record else None
