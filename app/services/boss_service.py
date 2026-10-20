from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
import logging
from typing import Callable, Optional, List
from app.database.models import Room, BossRecord, BossType
from app.schemas.boss import BossRecordResponse, BossRecordCreate
from app.services.notification_policy import NotificationPolicy
from app.utils.identity import Identity


class BossService:

    @staticmethod
    def get_room_records_history(
        db: Session,
        room_id: str,
        before_id: Optional[int] = None,
        limit: int = 50,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        boss_type_id: Optional[int] = None,
    ) -> tuple[List[BossRecord], bool]:
        """撈取房間歷史紀錄（cursor-based，依 id desc）。多撈 1 筆判斷是否還有更多。"""
        query = db.query(BossRecord).options(
            joinedload(BossRecord.recorder),
            joinedload(BossRecord.boss_type),
        ).filter(
            BossRecord.room_id == room_id,
            BossRecord.is_archived == False,
        )
        if before_id is not None:
            query = query.filter(BossRecord.id < before_id)
        if start is not None:
            query = query.filter(BossRecord.recorded_at >= start)
        if end is not None:
            query = query.filter(BossRecord.recorded_at <= end)
        if boss_type_id is not None:
            query = query.filter(BossRecord.boss_type_id == boss_type_id)

        rows = query.order_by(BossRecord.id.desc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    @staticmethod
    def _validate_room_exists(db: Session, room_id: str) -> Room:
        """驗證房間是否存在"""
        room = db.query(Room).filter(Room.room_id == room_id, Room.is_active == True).first()
        if not room:
            raise HTTPException(status_code=404, detail=f"房間 {room_id} 不存在")
        return room  # type: ignore

    @staticmethod
    def _get_boss_type_by_id(db: Session, boss_type_id: int) -> BossType:
        """驗證 BOSS 類型是否存在"""
        boss_type = db.query(BossType).filter(BossType.id == boss_type_id).first()
        if not boss_type:
            raise HTTPException(status_code=400, detail="Invalid boss type")
        return boss_type  # type: ignore

    @staticmethod
    def _calculate_respawn_times(
            db: Session,
            record: BossRecordCreate,
            boss_type: BossType
    ) -> dict:
        """計算 BOSS 重生時間"""
        now = datetime.now(timezone.utc)

        if record.status == "killed":
            base_time = now
        else:
            # alive / not_found 不計算重生時間
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
    def _create_boss_record(
            db: Session,
            record: BossRecordCreate,
            respawn_times: dict,
            identity: Identity
    ) -> BossRecord:
        """
        記錄者以伺服器端的身分為準（見 docs/adr/0007）：登入者寫 recorder_id；匿名者的 anonymous_id 取自
        伺服器簽發的 cookie，前端送來的 anonymous_id 一律忽略（匿名 UUID 會廣播給房間所有人，採信前端就能冒用他人）。
        暱稱仍由前端提供。
        """
        recorder_id_to_save = None
        recorder_info_to_save = None

        if identity.kind == "user":
            recorder_id_to_save = int(identity.id)
        else:
            anonymous_id = identity.id if identity.kind == "anon" else None
            anonymous_name = record.recorder_info.anonymous_name if record.recorder_info else None
            if anonymous_id or anonymous_name:
                recorder_info_to_save = {"anonymous_id": anonymous_id, "anonymous_name": anonymous_name}

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
    def record_boss(db: Session, record: BossRecordCreate, identity: Identity, broadcast: Callable[[dict], None]) -> None:
        """
        寫入 WebSocket 回報的紀錄，以 broadcast 廣播 boss_update 給房間，再排程 Discord 通知。
        同步執行、會查資料庫：呼叫端經 run_db() 執行（拿資料庫鎖、在 threadpool），broadcast 負責回到 event loop 上廣播（ADR-0010）。
        先廣播再排程：排程要寫 Redis，Redis 慢的時候房間不該等它才看到回報
        """
        room = BossService._validate_room_exists(db, record.room_id)
        room.last_active = datetime.now(timezone.utc)
        boss_type = BossService._get_boss_type_by_id(db, record.boss_type_id)
        respawn_times = BossService._calculate_respawn_times(db, record, boss_type)
        boss_record = BossService._create_boss_record(db, record, respawn_times, identity)

        record_with_recorder = db.query(BossRecord).options(
            joinedload(BossRecord.recorder),
            joinedload(BossRecord.boss_type)
        ).filter(BossRecord.id == boss_record.id).first()

        if not record_with_recorder:
            logging.error(f"Could not find boss_record with id {boss_record.id} to broadcast update.")
            return

        broadcast({
            "type": "boss_update",
            "data": BossRecordResponse.model_validate(record_with_recorder).model_dump(mode='json'),
        })
        NotificationPolicy.notify(record_with_recorder, room, db)
