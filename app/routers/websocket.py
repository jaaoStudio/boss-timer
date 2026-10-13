# app/routers/websocket.py
import json
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import models
from app.database.database import SessionLocal
from app.services import auth_service, room_service, boss_service
from app.dependencies import IP_CEILING_MULTIPLIER, check_dual_limit, get_connection_manager, limit_keys
from app.utils import anonymous_id
from app.utils.identity import Identity
from app.websocket.manager import ConnectionManager
from app.schemas.boss import BossRecordCreate

router = APIRouter(prefix="/ws", tags=["websocket"])

# 限流（見 docs/adr/0007）：個人額度以伺服器端身分計算（重連不會歸零），IP 天花板為其 IP_CEILING_MULTIPLIER 倍
RECORD_BOSS_LIMIT = "30/minute;1000/day"
# 握手頻率：以身分計，所有分頁共用。約每小時 1000 次；用 10 分鐘的時間窗，撞到上限後最多 10 分鐘就恢復
# （固定時間窗，1 小時的窗最壞要等近 1 小時）。原本為背景分頁反覆重連（#43）而放寬，#43 已修，
# 部署後觀察正式環境的重連頻率再收緊
HANDSHAKE_LIMIT = "170/10 minutes"
# 同時連線數（多開分頁、手機加電腦）
MAX_CONNECTIONS = 10
# 超過連線限制時以此 close code 關閉，前端據此顯示提示
CLOSE_CODE_LIMITED = 4429


@router.get("/connections/count")
async def get_connections_count(manager: ConnectionManager = Depends(get_connection_manager)):
    return {"count": manager.get_total_connections()}

# 連線的身分與限流 key 在握手時決定，整條連線固定不變（登入 / 登出時前端會重新連線）
@dataclass(frozen=True)
class Connection:
    identity: Identity
    limit_keys: tuple[str, str]


Handler = Callable[[WebSocket, dict, Optional[str], Session, ConnectionManager, Connection], Awaitable[None]]


async def _handle_join_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, conn: Connection) -> None:
    if not room_service.get_room_by_id(db, room_id):
        await websocket.send_text(json.dumps({"type": "error", "code": "room_not_found", "message": "Room not found"}))
        return
    room_service.update_room_last_active(db, room_id)
    manager.subscribe_to_room(websocket, room_id)
    initial_state = room_service.get_room_state(db, room_id)
    await websocket.send_text(json.dumps(initial_state, default=str))
    await manager.broadcast_user_count(room_id)


async def _handle_leave_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, conn: Connection) -> None:
    manager.unsubscribe_from_room(websocket)
    await manager.broadcast_user_count(room_id)


async def _handle_record_boss(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, conn: Connection) -> None:
    current_room = manager.socket_to_room.get(websocket)
    if not current_room or current_room != room_id:
        await websocket.send_text(json.dumps({"type": "error", "code": "record_rejected", "message": "You are not in this room"}))
        return
    if not check_dual_limit(RECORD_BOSS_LIMIT, "ws_record_boss", conn.limit_keys):
        await websocket.send_text(json.dumps({"type": "error", "code": "rate_limited", "message": "Rate limit exceeded. Please slow down."}))
        return
    try:
        record_create = BossRecordCreate(**payload)
        await boss_service.BossService.record_boss_from_websocket(db, record_create, conn.identity, manager)
    except Exception as e:
        logging.error(f"Error processing record_boss message: {e}", exc_info=True)
        await websocket.send_text(json.dumps({"type": "error", "code": "record_rejected", "message": str(e)}))


_HANDLERS: dict[str, Handler] = {
    "join_room": _handle_join_room,
    "leave_room": _handle_leave_room,
    "record_boss": _handle_record_boss,
}


async def handle_message(websocket: WebSocket, message: dict, db: Session, manager: ConnectionManager, conn: Connection) -> None:
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

    await handler(websocket, payload, room_id, db, manager, conn)


async def _reject_connection(websocket: WebSocket) -> None:
    """
    超過握手頻率或同時連線數：接受後立即以明確的 close code 關閉，前端據此顯示提示。
    不另送錯誤訊息：前端收到伺服器訊息就會重置重連次數，被拒絕時不該重置。
    """
    await websocket.accept()
    await websocket.close(code=CLOSE_CODE_LIMITED, reason="connection_limited")


def _user_exists(db: Session, user_id: str) -> bool:
    return db.get(models.User, int(user_id)) is not None


def _resolve_handshake_identity(websocket: WebSocket) -> Identity:
    """
    WebSocket 握手時的身分。連線會存活很久，背景分頁也會在 access token（30 分鐘，cookie 同時到期）
    過期後自動重連，若只看 access token，登入者重連後會變成匿名、回報沒有記錄者。因此：
    1. access token 有效且使用者仍存在 → 登入者
    2. 否則 refresh token 有效（資料庫確認未撤銷；使用者刪除時一併刪除）→ 登入者
    3. 否則伺服器簽發的匿名身分 → 4. 無
    """
    cookies = websocket.cookies
    access_user = auth_service.decode_token_user_id(cookies.get("access_token"))
    refresh_token = cookies.get("refresh_token")
    if access_user or refresh_token:
        with SessionLocal() as db:
            if access_user and _user_exists(db, access_user):
                return Identity("user", access_user)
            if refreshed_user := auth_service.verify_refresh_token(db, refresh_token):
                return Identity("user", str(refreshed_user))
    if anon := anonymous_id.verify(cookies.get(anonymous_id.COOKIE_NAME)):
        return Identity("anon", anon)
    return Identity("none")


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: ConnectionManager = Depends(get_connection_manager)
):
    identity = _resolve_handshake_identity(websocket)
    conn = Connection(identity, limit_keys(identity, websocket))
    if not check_dual_limit(HANDSHAKE_LIMIT, "ws_handshake", conn.limit_keys) or not manager.try_reserve(
        websocket, conn.limit_keys, MAX_CONNECTIONS, MAX_CONNECTIONS * IP_CEILING_MULTIPLIER
    ):
        await _reject_connection(websocket)
        return

    try:
        await manager.connect(websocket)
    except Exception:
        manager.disconnect(websocket)   # 釋放 try_reserve 計入的連線數
        raise

    try:
        while True:
            # 不設接收逾時：死連線由協定層 ping 偵測，勿以「多久沒收到前端訊息」判斷生死（ADR-0008、#43）
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")

            if message_type == "ping":
                # 前端的探測（看門狗、送出訊息後）：回 pong 讓它確認連線仍通（ADR-0008）
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if message_type in ("authenticate", "deauthenticate"):
                # 已不再使用：身分改由握手時的 cookie 決定。部署切換期間仍開著的舊版前端可能送出，
                # 直接忽略（不進 handle_message，避免開 DB session）
                continue

            with SessionLocal() as db:
                await handle_message(websocket, message, db, manager, conn)

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