# app/database/models.py
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, ForeignKey, Index, Boolean,
    CheckConstraint, func, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(100))
    avatar_url = Column(Text)
    preferences = Column(JSONB, default={})
    is_admin = Column(Boolean, default=False, nullable=False) # 新增管理員欄位
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    records = relationship("BossRecord", back_populates="recorder")
    room_associations = relationship("RoomUser", back_populates="user")

    # 關聯
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String(10), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, nullable=False)

    boss_records = relationship("BossRecord", back_populates="room", cascade="all, delete-orphan")
    user_associations = relationship("RoomUser", back_populates="room", cascade="all, delete-orphan")


class BossType(Base):
    __tablename__ = "boss_types"

    boss_name = Column(String(50), primary_key=True)
    min_respawn_minutes = Column(Integer, nullable=False)
    max_respawn_minutes = Column(Integer, nullable=False)
    description = Column(Text)

    records = relationship("BossRecord", back_populates="boss_type")


class BossRecord(Base):
    __tablename__ = "boss_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=False)
    channel = Column(Integer, nullable=False)
    boss_name = Column(String(50), ForeignKey("boss_types.boss_name"), nullable=False)
    status = Column(String(20), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    respawn_min_time = Column(DateTime(timezone=True))
    respawn_max_time = Column(DateTime(timezone=True))
    recorder_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    recorder_info = Column(JSONB)
    is_archived = Column(Boolean, default=False, nullable=False)

    @property
    def current_status(self) -> str:
        now = datetime.now(timezone.utc)
        if self.status == "killed":
            if self.respawn_max_time and now >= self.respawn_max_time:
                return "alive"
            if self.respawn_min_time and now >= self.respawn_min_time:
                return "may_respawn"
            return "respawning"
        return self.status

    __table_args__ = (
        CheckConstraint('channel >= 1', name='check_channel_range'),
        CheckConstraint("status IN ('alive', 'killed', 'not_found')", name='check_status_values'),
        Index('idx_boss_records_room_channel', 'room_id', 'channel'),
        Index('idx_boss_records_room_boss', 'room_id', 'boss_name'),
        Index('idx_boss_records_time', 'recorded_at'),
        Index('idx_boss_records_recorder_id', 'recorder_id'),
    )

    room = relationship("Room", back_populates="boss_records")
    boss_type = relationship("BossType", back_populates="records")
    recorder = relationship("User", back_populates="records")


class RoomUser(Base):
    __tablename__ = "room_users"

    id = Column(BigInteger, primary_key=True)
    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    anonymous_session_id = Column(String(100))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint('user_id IS NOT NULL OR anonymous_session_id IS NOT NULL', name='chk_user_or_anonymous'),
        Index('idx_room_users_room_id', 'room_id'),
        Index('idx_room_users_user_id', 'user_id'),
    )

    room = relationship("Room", back_populates="user_associations")
    user = relationship("User", back_populates="room_associations")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    jti = Column(String, unique=True, index=True)  # JWT ID
    token = Column(Text)
    expires_at = Column(DateTime)
    created_at = Column(DateTime)

    # 關聯
    user = relationship("User", back_populates="refresh_tokens")