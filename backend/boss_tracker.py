from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, text, ForeignKey, Index, CheckConstraint
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
        CheckConstraint('channel >= 1 AND channel <= 30', name='check_channel_range'),
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
    recorded_at: datetime
    respawn_min_time: Optional[datetime]
    respawn_max_time: Optional[datetime]
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
        # websocket -> room_id mapping
        self.connection_rooms: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()

        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()

        self.room_connections[room_id].add(websocket)
        self.connection_rooms[websocket] = room_id

        # 更新資料庫
        await self.update_room_user_count(room_id)

    def disconnect(self, websocket: WebSocket):
        room_id = self.connection_rooms.get(websocket)
        if room_id:
            self.room_connections[room_id].discard(websocket)
            del self.connection_rooms[websocket]

            if not self.room_connections[room_id]:
                del self.room_connections[room_id]

            # 異步更新用戶數量
            asyncio.create_task(self.update_room_user_count(room_id))

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
                if connection in self.connection_rooms:
                    del self.connection_rooms[connection]

    async def update_room_user_count(self, room_id: str):
        user_count = len(self.room_connections.get(room_id, set()))

        db = SessionLocal()
        try:
            # 更新房間用戶數
            room = db.query(Room).filter(Room.room_id == room_id).first()
            if room:
                room.active_users = user_count
                room.last_active = datetime.utcnow()
                db.commit()

                # 廣播用戶數更新
                await self.broadcast_to_room(room_id, {
                    "type": "user_count_update",
                    "count": user_count
                })
        finally:
            db.close()


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
    await manager.connect(websocket, room_id)

    try:
        # 確保房間存在
        room = db.query(Room).filter(Room.room_id == room_id).first()
        if not room:
            room = Room(room_id=room_id)
            db.add(room)
            db.commit()

        # 發送當前房間狀態
        current_state = get_room_state(db, room_id)
        await websocket.send_text(json.dumps({
            "type": "room_state",
            "data": [record.__dict__ for record in current_state]
        }, default=str))

        # 處理消息
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# REST API 端點

@app.post("/api/record-boss")
async def record_boss(record: BossRecordCreate, db: Session = Depends(get_db)):
    try:
        # 獲取 BOSS 類型
        boss_type = db.query(BossType).filter(BossType.boss_name == record.boss_name).first()
        if not boss_type:
            raise HTTPException(status_code=400, detail="Invalid boss type")

        # 計算重生時間
        respawn_min_time = None
        respawn_max_time = None

        if record.status == "killed":
            now = datetime.utcnow()
            respawn_min_time = now + timedelta(minutes=boss_type.min_respawn_minutes)
            respawn_max_time = now + timedelta(minutes=boss_type.max_respawn_minutes)

        # 創建記錄
        boss_record = BossRecord(
            room_id=record.room_id,
            channel=record.channel,
            boss_name=record.boss_name,
            status=record.status,
            respawn_min_time=respawn_min_time,
            respawn_max_time=respawn_max_time
        )

        db.add(boss_record)
        db.commit()
        db.refresh(boss_record)

        # 更新房間活動時間
        room = db.query(Room).filter(Room.room_id == record.room_id).first()
        if room:
            room.last_active = datetime.utcnow()
            db.commit()

        # 廣播更新
        record_dict = boss_record.__dict__.copy()
        record_dict.update({
            "min_respawn_minutes": boss_type.min_respawn_minutes,
            "max_respawn_minutes": boss_type.max_respawn_minutes,
            "current_status": get_current_status(boss_record, boss_type)
        })

        await manager.broadcast_to_room(record.room_id, {
            "type": "boss_update",
            "data": record_dict
        })

        return {"success": True, "data": record_dict}

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
                "current_status": get_current_status(boss_record, boss_type)
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
        db.func.max(BossRecord.id).label('max_id')
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
            "current_status": get_current_status(boss_record, boss_type)
        })
        records.append(record_dict)

    return records


def get_current_status(boss_record: BossRecord, boss_type: BossType) -> str:
    if boss_record.status == "killed":
        now = datetime.utcnow()
        if boss_record.respawn_min_time and now >= boss_record.respawn_min_time:
            return "may_respawn"
        elif boss_record.respawn_min_time and now < boss_record.respawn_min_time:
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

    uvicorn.run(app, host="0.0.0.0", port=1254, ssl_keyfile="/home/jack/PycharmProjects/boss-timing/vite-key.pem", ssl_certfile="/home/jack/PycharmProjects/boss-timing/vite.pem")