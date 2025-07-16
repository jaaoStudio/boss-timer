# app/websocket/manager.py
import json
import logging
import asyncio
from typing import Dict, Set, Optional, Tuple
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.services import room_service

class ConnectionManager:
    def __init__(self):
        # room_id -> set of WebSockets
        self.room_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> (room_id, user_id, anonymous_id)
        self.connection_info: Dict[WebSocket, Tuple[str, Optional[int], Optional[str]]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        db: Session,
        user_id: Optional[int],
        anonymous_id: Optional[str]
    ):
        await websocket.accept()

        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(websocket)
        self.connection_info[websocket] = (room_id, user_id, anonymous_id)

        try:
            room_service.upsert_room_user(db, room_id, user_id, anonymous_id)
            logging.info(f"User presence updated for room {room_id}.")
        except Exception as e:
            db.rollback()
            logging.error(f"Error upserting user in room {room_id}: {e}", exc_info=True)

    async def disconnect(
        self,
        websocket: WebSocket,
        room_id: str,
        db: Session,
        user_id: Optional[int],
        anonymous_id: Optional[str]
    ):
        if room_id in self.room_connections:
            self.room_connections[room_id].discard(websocket)
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
                logging.info(f"Room {room_id} is now empty.")

        if websocket in self.connection_info:
            del self.connection_info[websocket]

        try:
            room_service.remove_room_user(db, room_id, user_id, anonymous_id)
            logging.info(f"User presence removed for room {room_id}.")
        except Exception as e:
            db.rollback()
            logging.error(f"Error removing user from room {room_id}: {e}", exc_info=True)

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.room_connections:
            message_str = json.dumps(message, default=str)
            # 使用 asyncio.gather 來並行發送訊息
            await asyncio.gather(
                *[conn.send_text(message_str) for conn in self.room_connections[room_id]],
                return_exceptions=True
            )

    async def broadcast_user_count(self, room_id: str, db: Session):
        try:
            count = room_service.get_room_user_count(db, room_id)
            await self.broadcast_to_room(room_id, {"type": "user_count_update", "count": count})
            logging.info(f"Broadcasted user count ({count}) for room {room_id}.")
        except Exception as e:
            logging.error(f"Error broadcasting user count for room {room_id}: {e}", exc_info=True)
