import asyncio
import logging
from datetime import datetime, timedelta, timezone
from app.database.database import SessionLocal
from app.database.models import BossRecord, Room


def archive_inactive_rooms() -> int:
    """封存 7 天不活躍的房間與其紀錄，回傳封存的房間數。同步、會查資料庫：在 threadpool 執行（ADR-0010）"""
    with SessionLocal() as db:
        cutoff_room = datetime.now(timezone.utc) - timedelta(days=7)
        room_ids = [room_id for (room_id,) in db.query(Room.room_id).filter(
            Room.last_active < cutoff_room, Room.is_active == True  # noqa: E712
        )]
        if room_ids:
            # 一次批次更新，不逐間房間載入紀錄
            db.query(Room).filter(Room.room_id.in_(room_ids)).update({Room.is_active: False}, synchronize_session=False)
            db.query(BossRecord).filter(BossRecord.room_id.in_(room_ids)).update(
                {BossRecord.is_archived: True}, synchronize_session=False
            )
        db.commit()
        return len(room_ids)


async def cleanup_inactive_rooms():
    while True:
        try:
            await asyncio.sleep(3600)  # 每小時執行一次
            # 查資料庫放進 threadpool：在 event loop 上執行會卡住所有 WebSocket 的心跳與廣播
            archived = await asyncio.to_thread(archive_inactive_rooms)
            logging.info(f"Marked {archived} inactive rooms as archived.")
        except Exception as e:
            logging.error(f"Cleanup error: {e}")
