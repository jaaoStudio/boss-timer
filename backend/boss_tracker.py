from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, text, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set
import asyncio
import json
import uuid
import logging
from contextlib import asynccontextmanager
from db_config import DATABASE_URL

# 資料庫配置
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 資料庫模型
class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String(10), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    active_users = Column(Integer, default=0)

    # 關聯
    boss_records = relationship("BossRecord", back_populates="room", cascade="all, delete-orphan")
    users = relationship("RoomUser", back_populates="room", cascade="all, delete-orphan")


class BossType(Base):
    __tablename__ = "boss_types"

    boss_name = Column(String(50), primary_key=True)
    min_respawn_minutes = Column(Integer, nullable=False)
    max_respawn_minutes = Column(Integer, nullable=False)
    description = Column(Text)

    # 關聯
    records = relationship("BossRecord", back_populates="boss_type")


class BossRecord(Base):
    __tablename__ = "boss_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=False)
    channel = Column(Integer, nullable=False)
    boss_name = Column(String(50), ForeignKey("boss_types.boss_name"), nullable=False)
    status = Column(String(20), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    respawn_min_time = Column(DateTime)
    respawn_max_time = Column(DateTime)
    recorder_info = Column(JSONB)

    # 約束
    __table_args__ = (
        CheckConstraint('channel >= 1', name='check_channel_range'),
        CheckConstraint("status IN ('alive', 'killed', 'not_found')", name='check_status_values'),
        Index('idx_boss_records_room_channel', 'room_id', 'channel'),
        Index('idx_boss_records_room_boss', 'room_id', 'boss_name'),
        Index('idx_boss_records_time', 'recorded_at'),
    )

    # 關聯
    room = relationship("Room", back_populates="boss_records")
    boss_type = relationship("BossType", back_populates="records")


class RoomUser(Base):
    __tablename__ = "room_users"

    room_id = Column(String(10), ForeignKey("rooms.room_id", ondelete="CASCADE"), primary_key=True)
    user_session = Column(String(100), primary_key=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # 關聯
    room = relationship("Room", back_populates="users")


# Pydantic 模型
class RoomCreate(BaseModel):
    room_id: str

class BossRecordCreate(BaseModel):
    room_id: str
    channel: int
    boss_name: str
    status: str


class BossRecordResponse(BaseModel):
    id: int
    room_id: str
    channel: int
    boss_name: str
    status: str
    recorded_at: str
    respawn_min_time: Optional[str]
    respawn_max_time: Optional[str]
    current_status: str
    min_respawn_minutes: int
    max_respawn_minutes: int


class BossTypeResponse(BaseModel):
    boss_name: str
    min_respawn_minutes: int
    max_respawn_minutes: int
    description: Optional[str]


# WebSocket 連接管理器
class ConnectionManager:
    def __init__(self):
        # room_id -> set of WebSocket connections
        self.room_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> (room_id, user_session) mapping
        self.connection_info: Dict[WebSocket, tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_session: str, db: Session):
        await websocket.accept()

        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(websocket)
        self.connection_info[websocket] = (room_id, user_session)

        logging.info(f"User {user_session} connecting to room {room_id}. Current connections: {len(self.room_connections[room_id])}")

        # 將用戶添加到 room_users 表
        try:
            room_user = db.query(RoomUser).filter_by(room_id=room_id, user_session=user_session).first()
            if not room_user:
                new_user = RoomUser(room_id=room_id, user_session=user_session)
                db.add(new_user)
                logging.info(f"Added new user {user_session} to room {room_id} in DB.")
            else:
                room_user.last_seen = datetime.utcnow()
                logging.info(f"Updated last_seen for user {user_session} in room {room_id}.")
            db.commit()
            logging.info(f"DB commit successful for user {user_session} in room {room_id}.")
        except Exception as e:
            db.rollback()
            logging.error(f"Error adding/updating user {user_session} in room {room_id} to DB: {e}")

        # 更新資料庫和廣播用戶數
        await self.update_room_user_count(room_id, db)

    async def disconnect(self, websocket: WebSocket, db: Session):
        room_id, user_session = self.connection_info.get(websocket, (None, None))
        if room_id and user_session:
            logging.info(f"User {user_session} disconnecting from room {room_id}.")
            self.room_connections[room_id].discard(websocket)
            del self.connection_info[websocket]

            # 從 room_users 表中刪除用戶
            try:
                deleted_count = db.query(RoomUser).filter_by(room_id=room_id, user_session=user_session).delete()
                db.commit()
                logging.info(f"Deleted {deleted_count} user {user_session} from room {room_id} in DB.")
            except Exception as e:
                db.rollback()
                logging.error(f"Error deleting user {user_session} from room {room_id} from DB: {e}")

            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
                logging.info(f"Room {room_id} has no more active WebSocket connections.")

            # 異步更新用戶數量
            asyncio.create_task(self.update_room_user_count(room_id, db))

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.room_connections:
            message_str = json.dumps(message, default=str)
            disconnected = set()

            for connection in self.room_connections[room_id]:
                try:
                    await connection.send_text(message_str)
                except:
                    disconnected.add(connection)

            # 清理斷開的連接
            for connection in disconnected:
                self.room_connections[room_id].discard(connection)
                if connection in self.connection_info:
                    del self.connection_info[connection]

    async def update_room_user_count(self, room_id: str, db: Session):
        # 從 room_users 表中獲取實際的活躍用戶數
        user_count = db.query(RoomUser).filter_by(room_id=room_id).count()
        logging.info(f"Updating user count for room {room_id}. Count from DB: {user_count}")

        try:
            # 更新房間用戶數
            room = db.query(Room).filter(Room.room_id == room_id).first()
            if room:
                room.active_users = user_count
                room.last_active = datetime.utcnow()
                db.commit()
                logging.info(f"Room {room_id} active_users updated to {user_count}.")

                # 廣播用戶數更新
                await self.broadcast_to_room(room_id, {
                    "type": "user_count_update",
                    "count": user_count
                })
                logging.info(f"Broadcasted user count {user_count} for room {room_id}.")
            else:
                logging.warning(f"Room {room_id} not found when updating user count.")
        except Exception as e:
            db.rollback()
            logging.error(f"Error updating room user count for room {room_id}: {e}")


# 初始化
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 用 SQL 文件初始化資料庫
    # init_db_from_sql_file(engine)

    # 啟動清理任務
    cleanup_task = asyncio.create_task(cleanup_inactive_rooms())

    yield

    # 關閉時清理
    cleanup_task.cancel()

def init_db_from_sql_file(engine, sql_file_path="schema.sql"):
    with engine.begin() as conn:
        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql = f.read()
            conn.execute(text(sql))
app = FastAPI(lifespan=lifespan)
manager = ConnectionManager()

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境應該限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 資料庫依賴
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# WebSocket 端點
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, db: Session = Depends(get_db)):
    user_session = str(uuid.uuid4())  # 為每個連接生成唯一的 session ID
    await manager.connect(websocket, room_id, user_session, db)

    try:
        # 確保房間存在
        room = db.query(Room).filter(Room.room_id == room_id).first()
        if not room:
            room = Room(room_id=room_id)
            db.add(room)
            db.commit()
            db.refresh(room)

        # 發送當前房間狀態和用戶數
        current_state = get_room_state(db, room_id)
        await websocket.send_text(json.dumps({
            "type": "room_state",
            "data": current_state
        }, default=str))
        
        # 立即發送用戶數更新
        await manager.update_room_user_count(room_id, db)

        # 處理消息
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        await manager.disconnect(websocket, db)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket, db)


# REST API 端點

@app.post("/api/room")
async def create_room(room_data: RoomCreate, db: Session = Depends(get_db)):
    try:
        room = db.query(Room).filter(Room.room_id == room_data.room_id).first()
        if room:
            return {"message": "Room already exists", "room_id": room.room_id}
        
        new_room = Room(room_id=room_data.room_id)
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return {"message": "Room created successfully", "room_id": new_room.room_id}
    except Exception as e:
        logging.error(f"Create room error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create room")

@app.post("/api/record-boss")
async def record_boss(record: BossRecordCreate, db: Session = Depends(get_db)):
    try:
        # 確保房間存在
        room = db.query(Room).filter(Room.room_id == record.room_id).first()
        if not room:
            room = Room(room_id=record.room_id)
            db.add(room)
            db.commit()
            db.refresh(room) # 刷新以確保 room 對象是最新的

        # 獲取 BOSS 類型
        boss_type = db.query(BossType).filter(BossType.boss_name == record.boss_name).first()
        if not boss_type:
            raise HTTPException(status_code=400, detail="Invalid boss type")

        # 計算重生時間
        respawn_min_time = None
        respawn_max_time = None
        now = datetime.utcnow()
        base_time = now # Default base time

        if record.status == "killed":
            # When killed, the recorded_at for this new record is 'now'
            # And respawn times are calculated from 'now'
            base_time = now
        elif record.status == "respawning":
            # When respawning, we need to find the recorded_at of the *last* 'killed' record
            last_killed_record = db.query(BossRecord).filter(
                BossRecord.room_id == record.room_id,
                BossRecord.channel == record.channel,
                BossRecord.boss_name == record.boss_name,
                BossRecord.status == "killed"
            ).order_by(BossRecord.recorded_at.desc()).first()

            if last_killed_record:
                base_time = last_killed_record.recorded_at
            else:
                # Fallback if no previous killed record is found (shouldn't happen if logic is followed)
                base_time = now

        if record.status == "killed" or record.status == "respawning":
            respawn_min_time = base_time + timedelta(minutes=boss_type.min_respawn_minutes)
            respawn_max_time = base_time + timedelta(minutes=boss_type.max_respawn_minutes)

        # Create record
        new_boss_record = BossRecord( # Renamed to new_boss_record to avoid confusion
            room_id=record.room_id,
            channel=record.channel,
            boss_name=record.boss_name,
            status=record.status,
            recorded_at=now, # The actual recorded_at for this new record
            respawn_min_time=respawn_min_time,
            respawn_max_time=respawn_max_time
        )

        db.add(new_boss_record)
        db.commit()
        db.refresh(new_boss_record)

        # Update room last_active
        room.last_active = datetime.utcnow()
        db.commit()

        # Broadcast update
        # Serialize new_boss_record using BossRecordResponse to exclude SQLAlchemy internal state
        boss_record_response = BossRecordResponse(
            id=new_boss_record.id,
            room_id=new_boss_record.room_id,
            channel=new_boss_record.channel,
            boss_name=new_boss_record.boss_name,
            status=new_boss_record.status,
            recorded_at=new_boss_record.recorded_at.isoformat() + 'Z',
            respawn_min_time=new_boss_record.respawn_min_time.isoformat() + 'Z' if new_boss_record.respawn_min_time else None,
            respawn_max_time=new_boss_record.respawn_max_time.isoformat() + 'Z' if new_boss_record.respawn_max_time else None,
            min_respawn_minutes=boss_type.min_respawn_minutes,
            max_respawn_minutes=boss_type.max_respawn_minutes,
            current_status=get_current_status(new_boss_record, boss_type)
        )

        await manager.broadcast_to_room(record.room_id, {
            "type": "boss_update",
            "data": boss_record_response.__dict__
        })

        logging.info(f"Broadcasted boss_update for room {record.room_id}: {boss_record_response}")

        return {"success": True, "data": boss_record_response}

    except Exception as e:
        logging.error(f"Record boss error: {e}")
        raise HTTPException(status_code=500, detail="Failed to record boss status")


@app.get("/api/room/{room_id}/history")
async def get_room_history(
        room_id: str,
        boss_name: Optional[str] = None,
        limit: int = 50,
        db: Session = Depends(get_db)
):
    try:
        query = db.query(BossRecord, BossType).join(BossType).filter(BossRecord.room_id == room_id)

        if boss_name:
            query = query.filter(BossRecord.boss_name == boss_name)

        results = query.order_by(BossRecord.recorded_at.desc()).limit(limit).all()

        records = []
        for boss_record, boss_type in results:
            record_dict = boss_record.__dict__.copy()
            record_dict.update({
                "min_respawn_minutes": boss_type.min_respawn_minutes,
                "max_respawn_minutes": boss_type.max_respawn_minutes,
                "current_status": get_current_status(boss_record, boss_type),
                "recorded_at": boss_record.recorded_at.isoformat() + 'Z',
                "respawn_min_time": boss_record.respawn_min_time.isoformat() + 'Z' if boss_record.respawn_min_time else None,
                "respawn_max_time": boss_record.respawn_max_time.isoformat() + 'Z' if boss_record.respawn_max_time else None,
            })
            records.append(record_dict)

        return records

    except Exception as e:
        logging.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history")


@app.get("/api/boss-types", response_model=List[BossTypeResponse])
async def get_boss_types(db: Session = Depends(get_db)):
    return db.query(BossType).all()


# 輔助函數
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
        record_dict = boss_record.__dict__.copy()
        record_dict.update({
            "min_respawn_minutes": boss_type.min_respawn_minutes,
            "max_respawn_minutes": boss_type.max_respawn_minutes,
            "current_status": get_current_status(boss_record, boss_type),
            "recorded_at": boss_record.recorded_at.isoformat() + 'Z',
            "respawn_min_time": boss_record.respawn_min_time.isoformat() + 'Z' if boss_record.respawn_min_time else None,
            "respawn_max_time": boss_record.respawn_max_time.isoformat() + 'Z' if boss_record.respawn_max_time else None,
        })
        records.append(record_dict)

    return records


def get_current_status(boss_record: BossRecord, boss_type: BossType) -> str:
    now = datetime.utcnow()

    if boss_record.status == "killed":
        if boss_record.respawn_max_time and now >= boss_record.respawn_max_time:
            return "alive" # Or some other status indicating it should have respawned
        if boss_record.respawn_min_time and now >= boss_record.respawn_min_time:
            return "may_respawn"
        return "respawning"

    return boss_record.status


# 清理任務
async def cleanup_inactive_rooms():
    while True:
        try:
            await asyncio.sleep(3600)  # 每小時執行一次

            db = SessionLocal()
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                db.query(Room).filter(Room.last_active < cutoff_time).delete()
                db.commit()
                logging.info("Cleaned up inactive rooms")
            finally:
                db.close()

        except Exception as e:
            logging.error(f"Cleanup error: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=1254, ssl_keyfile="/home/jack/PycharmProjects/boss-timing/frontend/vite-key.pem", ssl_certfile="/home/jack/PycharmProjects/boss-timing/frontend/vite.pem")