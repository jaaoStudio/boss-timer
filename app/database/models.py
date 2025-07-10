# app/database/models.py
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from app.database.database import Base

class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String(10), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    active_users = Column(Integer, default=0)

    boss_records = relationship("BossRecord", back_populates="room", cascade="all, delete-orphan")
    users = relationship("RoomUser", back_populates="room", cascade="all, delete-orphan")

class BossType(Base):
    __tablename__ = "boss_types"

    boss_name = Column(String(50), primary_key=True)
    min_respawn_minutes = Column(Integer, nullable=False)
    max_respawn_minutes = Column(Integer, nullable=False)
    description = Column(Text)

    records = relationship("BossRecord", back_populates="boss_type")

class BossRecord(Base):
    __tablename__ = "boss_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=False)
    channel = Column(Integer, nullable=False)
    boss_name = Column(String(50), ForeignKey("boss_types.boss_name"), nullable=False)
    status = Column(String(20), nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    respawn_min_time = Column(DateTime)
    respawn_max_time = Column(DateTime)
    recorder_info = Column(JSONB)

    __table_args__ = (
        CheckConstraint('channel >= 1', name='check_channel_range'),
        CheckConstraint("status IN ('alive', 'killed', 'not_found')", name='check_status_values'),
        Index('idx_boss_records_room_channel', 'room_id', 'channel'),
        Index('idx_boss_records_room_boss', 'room_id', 'boss_name'),
        Index('idx_boss_records_time', 'recorded_at'),
    )

    room = relationship("Room", back_populates="boss_records")
    boss_type = relationship("BossType", back_populates="records")

class RoomUser(Base):
    __tablename__ = "room_users"

    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), primary_key=True)
    user_session = Column(String(100), primary_key=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    room = relationship("Room", back_populates="users")