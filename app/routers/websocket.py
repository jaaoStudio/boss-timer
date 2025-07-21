# app/routers/websocket.py
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import models
from app.database.database import get_db
from app.services import room_service
from app.dependencies import get_current_user_from_ws, get_connection_manager
from app.websocket.manager import ConnectionManager
import logging

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.get("/connections/count")
async def get_connections_count(manager: ConnectionManager = Depends(get_connection_manager)):
    return {"count": manager.get_total_connections()}

@router.websocket("/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user_from_ws),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    處理 WebSocket 連線，支援已登入和匿名使用者。
    """
    # 確定使用者身份
    if current_user:
        user_id = current_user.id
        anonymous_id = None
        logging.info(f"User {user_id} connected to room {room_id}")
    else:
        user_id = None
        anonymous_id = str(uuid.uuid4())
        logging.info(f"Anonymous user {anonymous_id} connected to room {room_id}")

    # 連線前檢查
    if manager.get_total_connections() >= 1000:
        logging.warning("Connection limit reached. Rejecting new connection.")
        await websocket.accept()
        await websocket.close(code=1013, reason="Connection limit reached")
        return

    await websocket.accept()
    # 連線到管理器
    await manager.connect(websocket, room_id, db, user_id, anonymous_id)

    try:
        # 驗證房間是否存在
        if not room_service.get_room_by_id(db, room_id):
            await websocket.close(code=1008, reason="Room not found")
            return

        # 發送初始房間狀態
        initial_state = room_service.get_room_state(db, room_id)
        await websocket.send_text(json.dumps(initial_state, default=str))

        # 廣播更新後的用戶數
        await manager.broadcast_user_count(room_id, db)

        # 監聽訊息
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logging.info(f"Client disconnected from room {room_id}")
    except Exception as e:
        logging.error(f"WebSocket error in room {room_id}: {e}", exc_info=True)
    finally:
        # 確保無論如何都執行斷線邏輯
        await manager.disconnect(websocket, room_id, db, user_id, anonymous_id)
        await manager.broadcast_user_count(room_id, db)
