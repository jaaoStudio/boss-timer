# app/database/models.py
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, ForeignKey, Index, Boolean,
    CheckConstraint, UniqueConstraint, func, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from .database import Base


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

    # 關聯
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String(10), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, nullable=False)
    discord_webhook_url = Column(String(1000), nullable=True) # 新增 Discord Webhook
    discord_webhook_enabled = Column(Boolean, default=False, server_default='false', nullable=False) # Discord Webhook 全域開關
    webhook_notify_events = Column(JSONB, default=["killed", "alive", "not_found"]) # 擊殺/存活/找無通知開關
    webhook_alert_type = Column(String(20), default="none", nullable=True) # min, max, both, none

    boss_records = relationship("BossRecord", back_populates="room", cascade="all, delete-orphan")


class BossType(Base):
    __tablename__ = "boss_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=True)
    name_en = Column(String(50), nullable=False)
    name_zh = Column(String(50), nullable=False)
    min_respawn_minutes = Column(Integer, nullable=False)
    max_respawn_minutes = Column(Integer, nullable=False)
    description = Column(Text)

    records = relationship("BossRecord", back_populates="boss_type", passive_deletes=True)


class BossRecord(Base):
    __tablename__ = "boss_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=False)
    channel = Column(Integer, nullable=False)
    boss_type_id = Column(Integer, ForeignKey("boss_types.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    respawn_min_time = Column(DateTime(timezone=True))
    respawn_max_time = Column(DateTime(timezone=True))
    recorder_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    recorder_info = Column(JSONB)
    is_archived = Column(Boolean, default=False, nullable=False)
    celery_task_ids = Column(JSONB, nullable=True) # 記錄定時推播的 Task ID


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
        Index('idx_boss_records_room_boss_type', 'room_id', 'boss_type_id'),
        Index('idx_boss_records_time', 'recorded_at'),
        Index('idx_boss_records_recorder_id', 'recorder_id'),
        Index(
            'idx_boss_records_room_latest',
            'room_id', 'channel', 'boss_type_id', 'recorded_at',
        ),
        Index(
            'idx_boss_records_room_history',
            'room_id', 'id',
        ),
    )

    room = relationship("Room", back_populates="boss_records")
    boss_type = relationship("BossType", back_populates="records")
    recorder = relationship("User", back_populates="records")



class FeedbackItem(Base):
    __tablename__ = "feedback_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)  # 'bug' | 'feature'
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    # 'pending' | 'open' | 'planning' | 'done' | 'rejected'
    created_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('bug', 'feature')", name="check_feedback_type"),
        CheckConstraint(
            "status IN ('pending', 'open', 'planning', 'done', 'rejected')",
            name="check_feedback_status",
        ),
        Index("idx_feedback_items_status_created", "status", "created_at"),
        Index("idx_feedback_items_created_by", "created_by"),
    )

    creator = relationship("User", backref="feedback_items")
    votes = relationship(
        "FeedbackVote",
        back_populates="feedback",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FeedbackVote(Base):
    __tablename__ = "feedback_votes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    feedback_id = Column(
        BigInteger,
        ForeignKey("feedback_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("feedback_id", "user_id", name="uq_feedback_vote_user"),
        Index("idx_feedback_votes_feedback", "feedback_id"),
    )

    feedback = relationship("FeedbackItem", back_populates="votes")
    user = relationship("User")


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