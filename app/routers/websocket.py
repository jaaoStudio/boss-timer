# app/routers/websocket.py
import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.services import room_service, boss_service, auth_service
from app.dependencies import (
    IP_CEILING_MULTIPLIER,
    ceiling_limit_key,
    check_dual_limit,
    get_connection_manager,
    personal_limit_key,
)
from app.utils import anonymous_id
from app.utils.identity import Identity, resolve_identity
from app.websocket.manager import ConnectionManager
from app.schemas.boss import BossRecordCreate

router = APIRouter(prefix="/ws", tags=["websocket"])

# 限流（見 docs/adr/0007）：個人額度以伺服器端身分計算（重連不會歸零），IP 天花板為其 IP_CEILING_MULTIPLIER 倍
RECORD_BOSS_LIMIT = "30/minute;1000/day"
# 握手頻率：背景分頁目前每小時會重連數十次（#43），留一倍緩衝
HANDSHAKE_LIMIT = "120/hour"
# 同時連線數（多開分頁、手機加電腦）
MAX_CONNECTIONS = 10
# 超過連線限制時以此 close code 關閉，前端據此顯示提示
CLOSE_CODE_LIMITED = 4429

# --- Server-side heartbeat ---
# 客戶端每 30 秒送一次 ping，90 秒內沒有任何訊息視為靜默斷線
HEARTBEAT_TIMEOUT = 90  # seconds


@router.get("/connections/count")
async def get_connections_count(manager: ConnectionManager = Depends(get_connection_manager)):
    return {"count": manager.get_total_connections()}

Handler = Callable[[WebSocket, dict, Optional[str], Session, ConnectionManager, Identity], Awaitable[None]]


async def _handle_join_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, identity: Identity) -> None:
    if not room_service.get_room_by_id(db, room_id):
        await websocket.send_text(json.dumps({"type": "error", "code": "room_not_found", "message": "Room not found"}))
        return
    room_service.update_room_last_active(db, room_id)
    manager.subscribe_to_room(websocket, room_id)
    initial_state = room_service.get_room_state(db, room_id)
    await websocket.send_text(json.dumps(initial_state, default=str))
    await manager.broadcast_user_count(room_id)


async def _handle_leave_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, identity: Identity) -> None:
    manager.unsubscribe_from_room(websocket)
    await manager.broadcast_user_count(room_id)


async def _handle_record_boss(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, identity: Identity) -> None:
    current_room = manager.socket_to_room.get(websocket)
    if not current_room or current_room != room_id:
        await websocket.send_text(json.dumps({"type": "error", "code": "record_rejected", "message": "You are not in this room"}))
        return
    if not check_dual_limit(RECORD_BOSS_LIMIT, "ws_record_boss", identity, websocket):
        await websocket.send_text(json.dumps({"type": "error", "code": "rate_limited", "message": "Rate limit exceeded. Please slow down."}))
        return
    try:
        record_create = BossRecordCreate(**payload)
        await boss_service.BossService.record_boss_from_websocket(db, record_create, identity, manager)
    except Exception as e:
        logging.error(f"Error processing record_boss message: {e}", exc_info=True)
        await websocket.send_text(json.dumps({"type": "error", "code": "record_rejected", "message": str(e)}))


async def _handle_authenticate(websocket: WebSocket, message: dict, manager: ConnectionManager) -> None:
    token = message.get("token")
    if not token:
        return
    try:
        with SessionLocal() as db:
            new_user = auth_service.get_current_user_from_token(token, db)
    except HTTPException as e:
        logging.warning(f"WebSocket authentication failed: {e.detail}")
        return
    manager.set_identity(websocket, Identity("user", str(new_user.id)))
    logging.info(f"WebSocket re-authenticated for user_id: {new_user.id}")


async def _handle_deauthenticate(websocket: WebSocket, manager: ConnectionManager) -> None:
    manager.reset_identity(websocket)
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

    # 身分以 manager 為準（登入 / 登出會在連線中途切換）
    identity = manager.socket_identity.get(websocket, Identity("none"))
    await handler(websocket, payload, room_id, db, manager, identity)


async def _reject_connection(websocket: WebSocket) -> None:
    """超過握手頻率或同時連線數：接受後立即以明確的 close code 關閉，讓前端能顯示提示。"""
    await websocket.accept()
    await websocket.send_text(json.dumps({"type": "error", "code": "connection_limited", "message": "Too many connections."}))
    await websocket.close(code=CLOSE_CODE_LIMITED)


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: ConnectionManager = Depends(get_connection_manager)
):
    identity = resolve_identity(websocket)
    personal_key = personal_limit_key(identity, websocket)
    ceiling_key = ceiling_limit_key(identity, websocket)
    if not check_dual_limit(HANDSHAKE_LIMIT, "ws_handshake", identity, websocket) or not manager.has_capacity(
        personal_key, ceiling_key, MAX_CONNECTIONS, MAX_CONNECTIONS * IP_CEILING_MULTIPLIER
    ):
        await _reject_connection(websocket)
        return

    anon = anonymous_id.verify(websocket.cookies.get(anonymous_id.COOKIE_NAME))
    fallback_identity = Identity("anon", anon) if anon else Identity("none")
    await manager.connect(websocket, identity, fallback_identity, {personal_key, ceiling_key})

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
        if websocket in manager.socket_to_room:
            room_id = manager.socket_to_room[websocket]
            manager.disconnect(websocket)
            await manager.broadcast_user_count(room_id)
        else:
            manager.disconnect(websocket)