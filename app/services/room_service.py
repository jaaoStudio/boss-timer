# app/services/room_service.py
import secrets
import logging
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database.models import Room, RoomUser, BossRecord, BossType
from app.services.boss_service import BossService


class RoomService:
    @staticmethod
    def generate_unique_room_id(db: Session, length: int = 10, max_attempts: int = 20) -> str:
        """生成唯一的房間ID"""
        chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

        for attempt in range(max_attempts):
            room_id = ''.join(secrets.choice(chars) for _ in range(length))

            try:
                existing_room = db.query(Room).filter(Room.room_id == room_id).first()
                if not existing_room:
                    return room_id
            except Exception as e:
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    continue
                else:
                    raise e

        raise Exception(f"Unable to generate unique room ID after {max_attempts} attempts")

    @staticmethod
    def create_room(db: Session) -> Room:
        """創建新房間"""
        room_id = RoomService.generate_unique_room_id(db, length=10)

        new_room = Room(room_id=room_id)
        db.add(new_room)
        db.commit()
        db.refresh(new_room)

        logging.info(f"Created new room: {room_id}")
        return new_room

    @staticmethod
    def get_room_by_id(db: Session, room_id: str) -> Room:
        """根據ID獲取房間"""
        return db.query(Room).filter(Room.room_id == room_id.upper()).first()

    @staticmethod
    def update_room_last_active(db: Session, room: Room) -> None:
        """更新房間最後活躍時間"""
        room.last_active = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def add_user_to_room(db: Session, room_id: str, user_session: str) -> None:
        """添加用戶到房間"""
        room_user = db.query(RoomUser).filter_by(room_id=room_id, user_session=user_session).first()
        if not room_user:
            new_user = RoomUser(room_id=room_id, user_session=user_session)
            db.add(new_user)
            logging.info(f"Added new user {user_session} to room {room_id} in DB.")
        else:
            room_user.last_seen = datetime.now(timezone.utc)
            logging.info(f"Updated last_seen for user {user_session} in room {room_id}.")
        db.commit()

    @staticmethod
    def remove_user_from_room(db: Session, room_id: str, user_session: str) -> int:
        """從房間移除用戶，返回刪除的數量"""
        deleted_count = db.query(RoomUser).filter_by(room_id=room_id, user_session=user_session).delete()
        db.commit()
        return deleted_count

    @staticmethod
    def get_room_user_count(db: Session, room_id: str) -> int:
        """獲取房間用戶數量"""
        return db.query(RoomUser).filter_by(room_id=room_id).count()

    @staticmethod
    def update_room_user_count(db: Session, room_id: str) -> int:
        """更新房間用戶數量並返回最新數量"""
        user_count = RoomService.get_room_user_count(db, room_id)

        room = db.query(Room).filter(Room.room_id == room_id).first()
        if room:
            room.active_users = user_count
            room.last_active = datetime.now(timezone.utc)
            db.commit()
            logging.info(f"Room {room_id} active_users updated to {user_count}.")

        return user_count
    @staticmethod
    def get_room_state(db: Session, room_id: str):
        # 獲取每個頻道和 BOSS 的最新記錄
        subquery = db.query(
            BossRecord.channel,
            BossRecord.boss_name,
            func.max(BossRecord.id).label('max_id')
        ).filter(
            BossRecord.room_id == room_id
        ).group_by(
            BossRecord.channel,
            BossRecord.boss_name
        ).subquery()

        results = db.query(BossRecord, BossType).join(BossType).join(
            subquery,
            (BossRecord.id == subquery.c.max_id)
        ).all()

        records = []
        for boss_record, boss_type in results:
            records.append(BossService.serialize_boss_record(boss_record, boss_type))

        return records

    @staticmethod
    async def _update_room_last_active(db: Session, room: Room):
        """更新房間最後活躍時間"""
        room.last_active = datetime.now(timezone.utc)
        db.commit()