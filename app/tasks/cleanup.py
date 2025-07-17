import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import Room

async def cleanup_inactive_rooms():
    while True:
        try:
            await asyncio.sleep(3600)  # 每小時執行一次

            db = SessionLocal()
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                inactive_rooms = db.query(Room).filter(Room.last_active < cutoff_time, Room.is_active == True).all()
                for room in inactive_rooms:
                    room.is_active = False
                    for record in room.boss_records:
                        record.is_archived = True
                db.commit()
                logging.info(f"Marked {len(inactive_rooms)} inactive rooms and their records as inactive/archived.")
            finally:
                db.close()

        except Exception as e:
            logging.error(f"Cleanup error: {e}")