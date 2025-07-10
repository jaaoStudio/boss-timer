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
                db.query(Room).filter(Room.last_active < cutoff_time).delete()
                db.commit()
                logging.info("Cleaned up inactive rooms")
            finally:
                db.close()

        except Exception as e:
            logging.error(f"Cleanup error: {e}")