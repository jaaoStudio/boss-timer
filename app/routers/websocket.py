# app/routers/websocket.py
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.room_service import RoomService
from app.dependencies import get_current_user_from_ws, ConnectionManager, get_connection_manager
import logging


router = APIRouter(prefix="/ws", tags=["websocket_router"])


@router.websocket("/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_from_ws),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    await manager.connect(websocket, room_id, user_id, db)

    try:
        # 確保房間存在
        room = RoomService.get_room_by_id(db, room_id)
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
        current_state = RoomService.get_room_state(db, room_id)
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
