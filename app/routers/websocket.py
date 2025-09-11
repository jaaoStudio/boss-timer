# app/routers/websocket.py
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import models
from app.database.database import get_db
from app.services import room_service, boss_service, auth_service
from app.dependencies import get_current_user_from_ws, get_connection_manager
from app.websocket.manager import ConnectionManager
from app.schemas.boss import BossRecordCreate

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.get("/connections/count")
async def get_connections_count(manager: ConnectionManager = Depends(get_connection_manager)):
    return {"count": manager.get_total_connections()}

async def handle_message(websocket: WebSocket, message: dict, db: Session, manager: ConnectionManager, user_id: Optional[str]):
    msg_type = message.get("type")
    payload = message.get("payload", {})
    room_id = payload.get("room_id")

    if not msg_type:
        logging.warning("Received message without type")
        return

    if msg_type == "ping":
        await websocket.send_text(json.dumps({"type": "pong"}))
        return

    if not room_id:
        if msg_type not in ["authenticate", "deauthenticate"]:
             logging.warning(f"Received message type '{msg_type}' without room_id")
             return

    # Room-specific messages
    if msg_type == "join_room":
        if not room_service.get_room_by_id(db, room_id):
            await websocket.send_text(json.dumps({"type": "error", "message": "Room not found"}))
            return
        manager.subscribe_to_room(websocket, room_id)
        initial_state = room_service.get_room_state(db, room_id)
        await websocket.send_text(json.dumps(initial_state, default=str))
        await manager.broadcast_user_count(room_id)

    elif msg_type == "leave_room":
        manager.unsubscribe_from_room(websocket)
        await manager.broadcast_user_count(room_id)

    elif msg_type == "record_boss":
        try:
            # The payload now contains boss_type_id directly from the frontend
            record_create = BossRecordCreate(**payload)
            await boss_service.BossService.record_boss_from_websocket(db, record_create, user_id, manager)
        except Exception as e:
            logging.error(f"Error processing record_boss message: {e}", exc_info=True)
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))

@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user_from_ws),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    user_id = current_user.id if current_user else None
    await manager.connect(websocket, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")

            if message_type == "authenticate":
                token = message.get("token")
                if token:
                    try:
                        new_user = auth_service.get_current_user_from_token(token, db)
                        if new_user:
                            user_id = new_user.id
                            manager.update_user_id(websocket, user_id)
                            logging.info(f"WebSocket re-authenticated for user_id: {user_id}")
                    except Exception as e:
                        logging.warning(f"WebSocket authentication failed: {e}")
                continue

            elif message_type == "deauthenticate":
                user_id = None
                manager.update_user_id(websocket, None)
                logging.info("WebSocket de-authenticated.")
                continue

            await handle_message(websocket, message, db, manager, user_id)

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