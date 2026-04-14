from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from app.database.models import Room, BossRecord, BossType
from app.schemas.boss import BossRecordResponse, BossRecordCreate
from app.websocket.manager import ConnectionManager
from app.tasks.webhook_tasks import send_discord_webhook


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

            # Webhook Logic
            room = await BossService._validate_room_exists(db, record.room_id)
            if room.discord_webhook_url:
                webhook_url = room.discord_webhook_url
                alert_type = room.webhook_alert_type or "both"
                boss_name = boss_type.name_zh
                channel = record.channel
                recorder_name = record_with_recorder.recorder.display_name if record_with_recorder.recorder else "訪客"
                record_status = record.status.value
                
                # 1. Immediate Broadcast
                action_text = "擊殺了" if record_status == "killed" else ("標記存活" if record_status == "alive" else "找無王")
                msg_content = f"⚔️ **{recorder_name}** 在 **[{channel}頻]** {action_text} **[{boss_name}]**！"
                send_discord_webhook.delay(webhook_url, content=msg_content)
                
                # 2. Spawn Alert (5 mins before)
                celery_ids = {}
                if record_status == "killed":
                    now = datetime.now(timezone.utc)
                    if alert_type in ["min", "both"] and boss_record.respawn_min_time:
                        min_eta = boss_record.respawn_min_time - timedelta(minutes=5)
                        if min_eta > now:
                            alert_msg = f"⚠️ **[{boss_name}]** 將於 5 分鐘後在 **[{channel}頻]** 重生 (最短時間)！"
                            task = send_discord_webhook.apply_async(args=[webhook_url, alert_msg], eta=min_eta)
                            celery_ids["min_task_id"] = task.id
                            
                    if alert_type in ["max", "both"] and boss_record.respawn_max_time:
                        max_eta = boss_record.respawn_max_time - timedelta(minutes=5)
                        if max_eta > now:
                            alert_msg = f"⚠️ **[{boss_name}]** 將於 5 分鐘後在 **[{channel}頻]** 重生 (最長時間)！"
                            task = send_discord_webhook.apply_async(args=[webhook_url, alert_msg], eta=max_eta)
                            celery_ids["max_task_id"] = task.id
                
                if celery_ids:
                    boss_record.celery_task_ids = celery_ids
                    db.commit()

        except HTTPException as e:
            raise e
        except Exception as e:
            logging.error(f"Error in record_boss_from_websocket: {e}")
            raise e