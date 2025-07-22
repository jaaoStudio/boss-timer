from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Response
from sqlalchemy.orm import sessionmaker, Session, relationship, joinedload
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
        room = db.query(Room).filter(Room.room_id == room_id, Room.is_active == True).first()
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
            user_id: Optional[str]
    ) -> BossRecord:

        recorder_id_to_save = None
        recorder_info_to_save = None

        if user_id:
            recorder_id_to_save = int(user_id)
        else:
            recorder_info_to_save = record.recorder_info
        """創建 BOSS 記錄"""
        boss_record = BossRecord(
            room_id=record.room_id,
            channel=record.channel,
            boss_name=record.boss_name,
            status=record.status,
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
    async def _broadcast_boss_update(db: Session,
                                     room_id: str,
                                     boss_record_id: int):
        """
        廣播單一 BOSS 的更新。
        會重新查詢資料庫以確保包含完整的關聯資料 (如 recorder)。
        """

        # 1. 根據 ID 重新查詢，並使用 joinedload 預先載入 recorder 關聯

        record_with_recorder = db.query(BossRecord).options(

            joinedload(BossRecord.recorder)
        ).filter(BossRecord.id == boss_record_id).first()

        if not record_with_recorder:
            logging.error(f"Could not find boss_record with id {boss_record_id} to broadcast update.")
            return

        # 2. 使用 Pydantic 模型進行序列化，它會自動處理 recorder 和 recorder_info
        # model_validate 會自動呼叫 @property 來計算 current_status

        response_data = BossRecordResponse.model_validate(record_with_recorder)

        # 3. 廣播序列化後的 JSON 資料

        await get_connection_manager().broadcast_to_room(

            room_id=room_id,

            message={

                "type": "boss_update",
                # 使用 .model_dump(mode='json') 來確保 datetime 等物件被正確轉換為字串

                "data": response_data.model_dump(mode='json')
            }
        )

        logging.info(f"Broadcasted boss_update for room {room_id}: {response_data.model_dump_json()}")

    @staticmethod
    async def _get_last_killed_time(db: Session, record: BossRecordCreate) -> Optional[datetime]:
        """獲取最後一次被殺死的時間"""
        last_killed_record = db.query(BossRecord).filter(
            BossRecord.room_id == record.room_id,
            BossRecord.channel == record.channel,
            BossRecord.boss_name == record.boss_name,
            BossRecord.status == "killed",
            BossRecord.is_archived == False  # 只考慮未歸檔的紀錄
        ).order_by(BossRecord.recorded_at.desc()).first()

        return last_killed_record.recorded_at if last_killed_record else None

    @staticmethod
    async def record_boss_from_websocket(db: Session, record: BossRecordCreate, user_id: Optional[str], manager: ConnectionManager):
        """Handles boss recording initiated from a WebSocket message."""
        try:
            # Validation and calculation logic is reused from the original service
            room = await BossService._validate_room_exists(db, record.room_id)
            boss_type = await BossService._validate_boss_type_exists(db, record.boss_name)
            respawn_times = await BossService._calculate_respawn_times(db, record, boss_type)
            boss_record = await BossService._create_boss_record(db, record, respawn_times, user_id)

            # Instead of calling the old broadcast method, we get the full record data
            # and then use the manager passed from the websocket endpoint to broadcast.
            record_with_recorder = db.query(BossRecord).options(
                joinedload(BossRecord.recorder)
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
            # Re-raise HTTP exceptions to be potentially caught and sent to the client
            raise e
        except Exception as e:
            logging.error(f"Error in record_boss_from_websocket: {e}")
            # In a websocket context, we might not be able to raise HTTPException,
            # so we just log the error.
            raise e
