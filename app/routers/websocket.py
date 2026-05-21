# app/routers/websocket.py
import asyncio
import json
import logging
import time
from typing import Optional, Dict, Callable, Awaitable

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import models
from app.database.database import SessionLocal
from app.services import room_service, boss_service, auth_service
from app.dependencies import get_current_user_from_ws, get_connection_manager
from app.websocket.manager import ConnectionManager
from app.schemas.boss import BossRecordCreate

router = APIRouter(prefix="/ws", tags=["websocket"])

# --- Per-connection rate limiting for record_boss ---
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 30     # max record_boss messages per window

# --- Server-side heartbeat ---
# 客戶端每 30 秒送一次 ping，90 秒內沒有任何訊息視為靜默斷線
HEARTBEAT_TIMEOUT = 90  # seconds


class RateLimiter:
    def __init__(self):
        self._counts: Dict[WebSocket, int] = {}
        self._resets: Dict[WebSocket, float] = {}

    def is_allowed(self, ws: WebSocket) -> bool:
        now = time.time()
        if ws not in self._counts or now - self._resets.get(ws, 0) > RATE_LIMIT_WINDOW:
            self._counts[ws] = 0
            self._resets[ws] = now
        self._counts[ws] += 1
        return self._counts[ws] <= RATE_LIMIT_MAX

    def cleanup(self, ws: WebSocket):
        self._counts.pop(ws, None)
        self._resets.pop(ws, None)


_rate_limiter = RateLimiter()


@router.get("/connections/count")
async def get_connections_count(manager: ConnectionManager = Depends(get_connection_manager)):
    return {"count": manager.get_total_connections()}

Handler = Callable[[WebSocket, dict, Optional[str], Session, ConnectionManager, Optional[str]], Awaitable[None]]


async def _handle_join_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, user_id: Optional[str]) -> None:
    if not room_service.get_room_by_id(db, room_id):
        await websocket.send_text(json.dumps({"type": "error", "message": "Room not found"}))
        return
    room_service.update_room_last_active(db, room_id)
    manager.subscribe_to_room(websocket, room_id)
    initial_state = room_service.get_room_state(db, room_id)
    await websocket.send_text(json.dumps(initial_state, default=str))
    await manager.broadcast_user_count(room_id)


async def _handle_leave_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, user_id: Optional[str]) -> None:
    manager.unsubscribe_from_room(websocket)
    await manager.broadcast_user_count(room_id)


async def _handle_record_boss(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, user_id: Optional[str]) -> None:
    current_room = manager.socket_to_room.get(websocket)
    if not current_room or current_room != room_id:
        await websocket.send_text(json.dumps({"type": "error", "message": "You are not in this room"}))
        return
    if not _rate_limiter.is_allowed(websocket):
        await websocket.send_text(json.dumps({"type": "error", "message": "Rate limit exceeded. Please slow down."}))
        return
    try:
        record_create = BossRecordCreate(**payload)
        await boss_service.BossService.record_boss_from_websocket(db, record_create, user_id, manager)
    except Exception as e:
        logging.error(f"Error processing record_boss message: {e}", exc_info=True)
        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))


async def _handle_authenticate(websocket: WebSocket, message: dict, manager: ConnectionManager) -> None:
    token = message.get("token")
    if not token:
        return
    try:
        with SessionLocal() as db:
            new_user = auth_service.get_current_user_from_token(token, db)
            manager.update_user_id(websocket, new_user.id if new_user else None)
            logging.info(f"WebSocket re-authenticated for user_id: {new_user.id if new_user else None}")
    except Exception as e:
        logging.warning(f"WebSocket authentication failed: {e}")


async def _handle_deauthenticate(websocket: WebSocket, manager: ConnectionManager) -> None:
    manager.update_user_id(websocket, None)
    logging.info("WebSocket de-authenticated.")


_HANDLERS: dict[str, Handler] = {
    "join_room": _handle_join_room,
    "leave_room": _handle_leave_room,
    "record_boss": _handle_record_boss,
}


async def handle_message(websocket: WebSocket, message: dict, db: Session, manager: ConnectionManager) -> None:
    msg_type = message.get("type")
    if not msg_type:
        logging.warning("Received message without type")
        return

    handler = _HANDLERS.get(msg_type)
    if handler is None:
        logging.warning(f"Unknown message type: '{msg_type}'")
        return

    payload = message.get("payload", {})
    room_id = payload.get("room_id")
    if not room_id:
        logging.warning(f"Received message type '{msg_type}' without room_id")
        return

    # user_id is the single source of truth in manager — no local variable needed
    user_id = manager.socket_to_user.get(websocket)
    await handler(websocket, payload, room_id, db, manager, user_id)


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    current_user: Optional[models.User] = Depends(get_current_user_from_ws),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    await manager.connect(websocket, current_user.id if current_user else None)

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_TIMEOUT
                )
            except asyncio.TimeoutError:
                logging.info("WebSocket heartbeat timeout, closing dead connection.")
                try:
                    await websocket.close()
                except Exception:
                    pass
                break

            message = json.loads(data)
            message_type = message.get("type")

            if message_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if message_type == "authenticate":
                await _handle_authenticate(websocket, message, manager)
                continue

            if message_type == "deauthenticate":
                await _handle_deauthenticate(websocket, manager)
                continue

            with SessionLocal() as db:
                await handle_message(websocket, message, db, manager)

    except WebSocketDisconnect:
        logging.info(f"Client disconnected.")
    except Exception as e:
        logging.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        _rate_limiter.cleanup(websocket)
        if websocket in manager.socket_to_room:
            room_id = manager.socket_to_room[websocket]
            manager.disconnect(websocket)
            await manager.broadcast_user_count(room_id)
        else:
            manager.disconnect(websocket)