import asyncio
import logging
from datetime import datetime, timedelta, timezone
from app.database.database import SessionLocal
from app.database.models import Room

async def cleanup_inactive_rooms():
    while True:
        try:
            await asyncio.sleep(3600)  # 每小時執行一次

            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)

                # 封存 7 天不活躍的房間與其紀錄
                cutoff_room = now - timedelta(days=7)
                inactive_rooms = db.query(Room).filter(Room.last_active < cutoff_room, Room.is_active == True).all()
                for room in inactive_rooms:
                    room.is_active = False
                    for record in room.boss_records:
                        record.is_archived = True
                logging.info(f"Marked {len(inactive_rooms)} inactive rooms as archived.")

                db.commit()
            finally:
                db.close()

        except Exception as e:
            logging.error(f"Cleanup error: {e}")