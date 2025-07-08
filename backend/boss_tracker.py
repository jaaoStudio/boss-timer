from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, text, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship, InstrumentedAttribute
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Set, Any, Coroutine, Type
import asyncio
import json
import uuid
import logging
import os
import secrets
from contextlib import asynccontextmanager
from db_config import DATABASE_URL
from jose import JWTError, jwt


# 資料庫配置
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 資料庫模型
class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String(10), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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

# --- JWT ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

class TokenData(BaseModel):
    user_id: Optional[str] = None
# --- END JWT ---


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
                room_user.last_seen = datetime.now(timezone.utc)
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
                room.last_active = datetime.now(timezone.utc)
                db.commit()
                logging.info(f"Room {room_id} active_users updated to {user_count}.")

                # 廣播用戶數更新
                await self.broadcast_to_room(room_id, {
                    "type": "user_count_update",
                    "count": user_count
                })
                logging.info(f"Broadcast user count {user_count} for room {room_id}.")
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
    allow_origins=["https://boss-timer.jaao.tw"],  # 只允許您的前端域名
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

# --- JWT HELPERS & DEPENDENCY ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user_id(request: Request):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials, token missing or invalid",
    )
    token = request.cookies.get("access_token")

    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user_id
# --- END JWT HELPERS & DEPENDENCY ---


# WebSocket 端點
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, db: Session = Depends(get_db)):
    user_session = str(uuid.uuid4())  # 為每個連接生成唯一的 session ID
    await manager.connect(websocket, room_id, user_session, db)

    try:
        # 確保房間存在
        room = db.query(Room).filter(Room.room_id == room_id).first()
        if not room:
            # 房間不存在，發送錯誤訊息並關閉連接
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"房間 {room_id} 不存在",
                "error_code": "ROOM_NOT_FOUND"
            }))
            await websocket.close(code=1008, reason="Room not found")
            return

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

@app.post("/token", tags=["Authentication"])
async def login_for_access_token(response: Response):
    """
    Generate a new JWT for an anonymous user and set it in an HttpOnly cookie.
    """
    user_id = str(uuid.uuid4())
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite='lax',
        secure=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return {"status": "token set"}

@app.get("/health")
async def health_check():
    """
    健康檢查端點
    返回服務狀態和基本信息
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "boss_service",
        "version": os.getenv("VERSION"),
    }

def generate_unique_room_id(db: Session, length: int = 10, max_attempts: int = 10) -> str:
    """
    使用 secrets 生成唯一的房間ID

    Args:
        db: 資料庫會話
        length: ID長度 (預設8位，最大10位)
        max_attempts: 最大嘗試次數

    Returns:
        唯一的房間ID
    """
    # 移除容易混淆的字符 (0, O, I, 1, L)
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    max_attempts = 20

    for attempt in range(max_attempts):
        room_id = ''.join(secrets.choice(chars) for _ in range(length))

        try:
            # 直接嘗試查詢，讓 ORM 處理
            existing_room = db.query(Room).filter(Room.room_id == room_id).first()

            if not existing_room:
                return room_id

        except Exception as e:
            # 如果是唯一性約束錯誤，繼續嘗試
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            else:
                raise e

    raise Exception(f"Unable to generate unique room ID after {max_attempts} attempts")

@app.post("/room")
async def create_room(db: Session = Depends(get_db)):
    """
    創建新房間 - 自動生成唯一房間ID
    """
    try:
        # 生成唯一房間ID (8位)
        room_id = generate_unique_room_id(db, length=10)

        # 創建房間
        new_room = Room(room_id=room_id)
        db.add(new_room)
        db.commit()
        db.refresh(new_room)

        logging.info(f"Created new room: {room_id}")

        return {
            "success": True,
            "message": "Room created successfully",
            "room_id": room_id,
            "created_at": new_room.created_at.isoformat()
        }

    except Exception as e:
        db.rollback()

        # 區分不同類型的錯誤
        if "Unable to generate unique room ID" in str(e):
            logging.error(f"Room ID generation failed: {e}")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again."
            )
        else:
            logging.error(f"Create room error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create room"
            )


# 添加檢查房間是否存在的端點
@app.get("/room/{room_id}/exists")
async def check_room_exists(room_id: str, db: Session = Depends(get_db)):
    """
    檢查房間是否存在
    """
    try:
        room = db.query(Room).filter(Room.room_id == room_id.upper()).first()

        if room:
            return {
                "exists": True,
                "room_id": room.room_id,
                "created_at": room.created_at.isoformat(),
                "last_active": room.last_active.isoformat(),
                "active_users": room.active_users
            }
        else:
            raise HTTPException(
                status_code=404,
                detail= {
                    "exists": False,
                    "room_id": room_id.upper()
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Check room exists error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check room existence")


@app.post("/record-boss")
async def record_boss(
        record: BossRecordCreate,
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user_id)
):
    """記錄 BOSS 狀態"""
    try:
        # 驗證房間和 BOSS 類型
        room = await _validate_room_exists(db, record.room_id)
        boss_type = await _validate_boss_type_exists(db, record.boss_name)

        # 計算重生時間
        respawn_times = await _calculate_respawn_times(db, record, boss_type)

        # 創建 BOSS 記錄
        boss_record = await _create_boss_record(db, record, respawn_times, user_id)

        # 更新房間最後活躍時間
        await _update_room_last_active(db, room)

        # 廣播更新
        await _broadcast_boss_update(record.room_id, boss_record, boss_type)

        # 返回響應
        return _create_success_response(boss_record, boss_type)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Record boss error: {e}")
        raise HTTPException(status_code=500, detail="Failed to record boss status")


async def _validate_room_exists(db: Session, room_id: str) -> Type[Room]:
    """驗證房間是否存在"""
    room = db.query(Room).filter(Room.room_id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail=f"房間 {room_id} 不存在")
    return room


async def _validate_boss_type_exists(db: Session, boss_name: str) -> Type[BossType]:
    """驗證 BOSS 類型是否存在"""
    boss_type = db.query(BossType).filter(BossType.boss_name == boss_name).first()
    if not boss_type:
        raise HTTPException(status_code=400, detail="Invalid boss type")
    return boss_type


async def _calculate_respawn_times(
        db: Session,
        record: BossRecordCreate,
        boss_type: BossType
) -> dict:
    """計算 BOSS 重生時間"""
    now = datetime.now(timezone.utc)

    if record.status == "killed":
        base_time = now
    elif record.status == "respawning":
        base_time = await _get_last_killed_time(db, record) or now
    else:
        # 其他狀態不需要重生時間
        return {
            "respawn_min_time": None,
            "respawn_max_time": None,
            "base_time": now
        }

    return {
        "respawn_min_time": base_time + timedelta(minutes=boss_type.min_respawn_minutes),
        "respawn_max_time": base_time + timedelta(minutes=boss_type.max_respawn_minutes),
        "base_time": now
    }


async def _get_last_killed_time(db: Session, record: BossRecordCreate) -> InstrumentedAttribute | None:
    """獲取最後一次被殺死的時間"""
    last_killed_record = db.query(BossRecord).filter(
        BossRecord.room_id == record.room_id,
        BossRecord.channel == record.channel,
        BossRecord.boss_name == record.boss_name,
        BossRecord.status == "killed"
    ).order_by(BossRecord.recorded_at.desc()).first()

    return last_killed_record.recorded_at if last_killed_record else None


async def _create_boss_record(
        db: Session,
        record: BossRecordCreate,
        respawn_times: dict,
        user_id: str
) -> BossRecord:
    """創建 BOSS 記錄"""
    boss_record = BossRecord(
        room_id=record.room_id,
        channel=record.channel,
        boss_name=record.boss_name,
        status=record.status,
        recorded_at=respawn_times["base_time"],
        respawn_min_time=respawn_times["respawn_min_time"],
        respawn_max_time=respawn_times["respawn_max_time"],
        recorder_info={"user_id": user_id}
    )

    db.add(boss_record)
    db.commit()
    db.refresh(boss_record)

    return boss_record


async def _update_room_last_active(db: Session, room: Room):
    """更新房間最後活躍時間"""
    room.last_active = datetime.now(timezone.utc)
    db.commit()


def _create_boss_record_response(boss_record: BossRecord, boss_type: BossType) -> BossRecordResponse:
    """創建 BossRecordResponse 對象"""
    return BossRecordResponse(
        id=boss_record.id,
        room_id=boss_record.room_id,
        channel=boss_record.channel,
        boss_name=boss_record.boss_name,
        status=boss_record.status,
        recorded_at=boss_record.recorded_at.isoformat(),
        respawn_min_time=boss_record.respawn_min_time.isoformat() if boss_record.respawn_min_time else None,
        respawn_max_time=boss_record.respawn_max_time.isoformat() if boss_record.respawn_max_time else None,
        min_respawn_minutes=boss_type.min_respawn_minutes,
        max_respawn_minutes=boss_type.max_respawn_minutes,
        current_status=get_current_status(boss_record, boss_type)
    )


async def _broadcast_boss_update(room_id: str, boss_record: BossRecord, boss_type: BossType):
    """廣播 BOSS 更新"""
    boss_record_response = _create_boss_record_response(boss_record, boss_type)

    await manager.broadcast_to_room(room_id, {
        "type": "boss_update",
        "data": boss_record_response.__dict__
    })

    logging.info(f"Broadcasted boss_update for room {room_id}: {boss_record_response}")


def _create_success_response(boss_record: BossRecord, boss_type: BossType) -> dict:
    """創建成功響應"""
    boss_record_response = _create_boss_record_response(boss_record, boss_type)
    return {"success": True, "data": boss_record_response}


@app.get("/room/{room_id}/history")
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
            records.append(serialize_boss_record(boss_record, boss_type))

        return records

    except Exception as e:
        logging.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history")


@app.get("/boss-types", response_model=List[BossTypeResponse])
async def get_boss_types(db: Session = Depends(get_db)):
    return db.query(BossType).all()

def serialize_boss_record(boss_record: BossRecord, boss_type: BossType) -> dict:
    record_dict = boss_record.__dict__.copy()
    record_dict.update({
        "min_respawn_minutes": boss_type.min_respawn_minutes,
        "max_respawn_minutes": boss_type.max_respawn_minutes,
        "current_status": get_current_status(boss_record, boss_type),
        "recorded_at": boss_record.recorded_at.isoformat(),
        "respawn_min_time": boss_record.respawn_min_time.isoformat() if boss_record.respawn_min_time else None,
        "respawn_max_time": boss_record.respawn_max_time.isoformat() if boss_record.respawn_max_time else None,
    })
    return record_dict

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
        records.append(serialize_boss_record(boss_record, boss_type))

    return records


def get_current_status(boss_record: BossRecord, boss_type: BossType) -> str:
    now = datetime.now(timezone.utc)

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
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                db.query(Room).filter(Room.last_active < cutoff_time).delete()
                db.commit()
                logging.info("Cleaned up inactive rooms")
            finally:
                db.close()

        except Exception as e:
            logging.error(f"Cleanup error: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=1254, root_path="/api")
