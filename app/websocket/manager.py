# app/websocket/manager.py
import json
import logging
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
from sqlalchemy.orm import Session


class ConnectionManager:
    def __init__(self):
        self.room_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_info: Dict[WebSocket, tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_session: str, db: Session):
        from app.services.room_service import RoomService
        await websocket.accept()

        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(websocket)
        self.connection_info[websocket] = (room_id, user_session)

        logging.info(f"User {user_session} connecting to room {room_id}. Current connections: {len(self.room_connections[room_id])}")

        try:
            RoomService.add_user_to_room(db, room_id, user_session)
            await self.update_room_user_count(room_id, db)
        except Exception as e:
            db.rollback()
            logging.error(f"Error adding user {user_session} to room {room_id}: {e}")

    async def disconnect(self, websocket: WebSocket, db: Session):
        from app.services.room_service import RoomService
        room_id, user_session = self.connection_info.get(websocket, (None, None))
        if room_id and user_session:
            logging.info(f"User {user_session} disconnecting from room {room_id}.")
            self.room_connections[room_id].discard(websocket)
            del self.connection_info[websocket]

            try:
                deleted_count = RoomService.remove_user_from_room(db, room_id, user_session)
                logging.info(f"Deleted {deleted_count} user {user_session} from room {room_id} in DB.")
            except Exception as e:
                db.rollback()
                logging.error(f"Error deleting user {user_session} from room {room_id}: {e}")

            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
                logging.info(f"Room {room_id} has no more active WebSocket connections.")

            asyncio.create_task(self.update_room_user_count(room_id, db))

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.room_connections:
            try:
                message_str = json.dumps(message, default=str)
            except (TypeError, ValueError) as e:
                logging.error(f"Failed to serialize message for room {room_id}: {e}")
                return

            disconnected = set()
            for connection in self.room_connections[room_id]:
                try:
                    await connection.send_text(message_str)
                except Exception as e:
                    logging.error(f"Error sending to connection in room {room_id}: {e}")
                    disconnected.add(connection)

            for connection in disconnected:
                self.room_connections[room_id].discard(connection)
                if connection in self.connection_info:
                    del self.connection_info[connection]

    async def update_room_user_count(self, room_id: str, db: Session):
        from app.services.room_service import RoomService
        try:
            user_count = RoomService.update_room_user_count(db, room_id)
            await self.broadcast_to_room(room_id=room_id, message={
                "type": "user_count_update",
                "count": user_count
            })
            logging.info(f"Broadcast user count {user_count} for room {room_id}.")
        except Exception as e:
            logging.error(f"Error updating room user count for room {room_id}: {e}")