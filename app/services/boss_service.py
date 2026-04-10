from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from app.database.models import Room, BossRecord, BossType
from app.schemas.boss import BossRecordResponse, BossRecordCreate
from app.websocket.manager import ConnectionManager


class BossService:

    @staticmethod
    async def _validate_room_exists(db: Session, room_id: str) -> Room:
        """驗證房間是否存在"""
        room = db.query(Room).filter(Room.room_id == room_id, Room.is_active == True).first()
        if not room:
            raise HTTPException(status_code=404, detail=f"房間 {room_id} 不存在")
        return room  # type: ignore

    @staticmethod
    async def _get_boss_type_by_id(db: Session, boss_type_id: int) -> BossType:
        """驗證 BOSS 類型是否存在"""
        boss_type = db.query(BossType).filter(BossType.id == boss_type_id).first()
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
            user_id: Optional[str]
    ) -> BossRecord:

        recorder_id_to_save = None
        recorder_info_to_save = None

        if user_id:
            recorder_id_to_save = int(user_id)
        else:
            recorder_info_to_save = record.recorder_info.model_dump() if record.recorder_info else None

        """創建 BOSS 記錄"""
        boss_record = BossRecord(
            room_id=record.room_id,
            channel=record.channel,
            boss_type_id=record.boss_type_id,
            status=record.status.value,
            recorded_at=respawn_times["base_time"],
            respawn_min_time=respawn_times["respawn_min_time"],
            respawn_max_time=respawn_times["respawn_max_time"],
            recorder_id=recorder_id_to_save,
            recorder_info=recorder_info_to_save
        )

        db.add(boss_record)
        db.commit()
        db.refresh(boss_record)

        return boss_record

    @staticmethod
    async def _get_last_killed_time(db: Session, record: BossRecordCreate) -> Optional[datetime]:
        """獲取最後一次被殺死的時間"""
        last_killed_record = db.query(BossRecord).filter(
            BossRecord.room_id == record.room_id,
            BossRecord.channel == record.channel,
            BossRecord.boss_type_id == record.boss_type_id,
            BossRecord.status == "killed",
            BossRecord.is_archived == False  # 只考慮未歸檔的紀錄
        ).order_by(BossRecord.recorded_at.desc()).first()

        return last_killed_record.recorded_at if last_killed_record else None

    @staticmethod
    async def record_boss_from_websocket(db: Session, record: BossRecordCreate, user_id: Optional[str], manager: ConnectionManager):
        """Handles boss recording initiated from a WebSocket message."""
        try:
            await BossService._validate_room_exists(db, record.room_id)
            boss_type = await BossService._get_boss_type_by_id(db, record.boss_type_id)
            respawn_times = await BossService._calculate_respawn_times(db, record, boss_type)
            boss_record = await BossService._create_boss_record(db, record, respawn_times, user_id)

            record_with_recorder = db.query(BossRecord).options(
                joinedload(BossRecord.recorder),
                joinedload(BossRecord.boss_type)
            ).filter(BossRecord.id == boss_record.id).first()

            if not record_with_recorder:
                logging.error(f"Could not find boss_record with id {boss_record.id} to broadcast update.")
                return

            response_data = BossRecordResponse.model_validate(record_with_recorder)

            await manager.broadcast_to_room(
                room_id=record.room_id,
                message={
                    "type": "boss_update",
                    "data": response_data.model_dump(mode='json')
                }
            )
            logging.info(f"Broadcasted boss_update from websocket for room {record.room_id}")

        except HTTPException as e:
            raise e
        except Exception as e:
            logging.error(f"Error in record_boss_from_websocket: {e}")
            raise e