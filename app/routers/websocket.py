# app/routers/websocket.py
import json
import logging
from contextlib import suppress
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
        manager.send(websocket, {"type": "error", "code": "room_not_found", "message": "Room not found"})
        return
    room_service.update_room_last_active(db, room_id)
    # 取得初始狀態成功後才訂閱：出錯時（例如資料庫故障）連線保留，但不留在房間裡卻沒有初始狀態
    initial_state = room_service.get_room_state(db, room_id)
    manager.subscribe_to_room(websocket, room_id)
    manager.send(websocket, initial_state)
    await manager.broadcast_user_count(room_id)


async def _handle_leave_room(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, conn: Connection) -> None:
    manager.unsubscribe_from_room(websocket)
    await manager.broadcast_user_count(room_id)


async def _handle_record_boss(websocket: WebSocket, payload: dict, room_id: Optional[str], db: Session, manager: ConnectionManager, conn: Connection) -> None:
    current_room = manager.socket_to_room.get(websocket)
    if not current_room or current_room != room_id:
        manager.send(websocket, {"type": "error", "code": "record_rejected", "message": "You are not in this room"})
        return
    if not check_dual_limit(RECORD_BOSS_LIMIT, "ws_record_boss", conn.limit_keys):
        manager.send(websocket, {"type": "error", "code": "rate_limited", "message": "Rate limit exceeded. Please slow down."})
        return
    try:
        record_create = BossRecordCreate(**payload)
        await boss_service.BossService.record_boss_from_websocket(db, record_create, conn.identity, manager)
    except Exception as e:
        logging.error(f"Error processing record_boss message: {e}", exc_info=True)
        manager.send(websocket, {"type": "error", "code": "record_rejected", "message": str(e)})


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
    if not room_id or not isinstance(room_id, str):
        logging.warning(f"Received message type '{msg_type}' without a valid room_id")
        return

    await handler(websocket, payload, room_id, db, manager, conn)


async def _receive_message(websocket: WebSocket) -> Optional[dict]:
    """
    收下一則用戶端訊息並解析。無法解析時回傳 None：二進位 frame、不是 JSON 物件、
    type 不是字串（socket.io-parser 同樣把非字串事件名當成解析失敗）、payload 不是物件。
    用 receive() 而非 receive_text()：後者遇到二進位 frame、或寫出 task 已關閉連線時會拋例外，
    receive() 照常回傳對方的斷線訊息
    """
    raw = await websocket.receive()
    if raw["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(raw.get("code", 1000), raw.get("reason"))
    data = raw.get("text")
    if data is None:
        return None
    try:
        message = json.loads(data)
    except (ValueError, RecursionError):   # 極深的巢狀 JSON 拋 RecursionError
        return None
    if (
        not isinstance(message, dict)
        or not isinstance(message.get("type"), str)
        or not isinstance(message.get("payload", {}), dict)
    ):
        return None
    return message


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
    except (WebSocketDisconnect, OSError) as e:
        # 握手途中對方離開（accept 失敗），不是伺服器錯誤
        logging.info(f"WebSocket handshake aborted: {e!r}")
        manager.disconnect(websocket)   # 釋放 try_reserve 計入的連線數
        return
    except Exception:
        logging.error("WebSocket handshake failed", exc_info=True)
        manager.disconnect(websocket)
        with suppress(Exception):   # uvicorn 在 app 返回時不會關閉傳輸，不關的話前端以為還連著
            await websocket.close(code=1011)
        return

    close_code: Optional[int] = None
    try:
        while True:
            # 不設接收逾時：死連線由協定層 ping 偵測，勿以「多久沒收到前端訊息」判斷生死（ADR-0008、#43）
            message = await _receive_message(websocket)
            if message is None:
                # 照 engine.io：只有封包解析失敗才關閉連線
                logging.info("Malformed WebSocket message, closing.")
                close_code = 1007
                break
            message_type = message.get("type")

            if message_type == "ping":
                # 新版前端不再送 ping（改由伺服器心跳，ADR-0008）；部署切換期間的舊版前端仍會送，照舊回 pong
                manager.send(websocket, {"type": "pong"})
                continue

            if message_type in ("authenticate", "deauthenticate"):
                # 已不再使用：身分改由握手時的 cookie 決定。部署切換期間仍開著的舊版前端可能送出，
                # 直接忽略（不進 handle_message，避免每則都記一筆 Unknown message type 警告）
                continue

            try:
                with SessionLocal() as db:
                    await handle_message(websocket, message, db, manager, conn)
            except Exception:
                # 照 Socket.IO：單則訊息處理出錯不關閉連線。關閉的話前端重連後 hello 會重置退避，
                # 每次都送 join_room、每次都出錯（例如資料庫故障），變成每秒重連一次
                logging.error(f"Error handling WebSocket message '{message_type}'", exc_info=True)

    except WebSocketDisconnect:
        logging.info(f"Client disconnected.")
    except Exception as e:
        logging.error(f"WebSocket error: {e}", exc_info=True)
        close_code = 1011
    finally:
        room_id = manager.socket_to_room.get(websocket)
        manager.disconnect(websocket)
        if room_id:
            await manager.broadcast_user_count(room_id)
        if close_code is not None:
            # 先清理再關閉：關閉握手可能要等 10 秒以上，期間不該還算在房間與人數裡。
            # uvicorn 在 app 返回時不會關閉傳輸，不關的話前端以為還連著，回報無聲遺失
            with suppress(Exception):
                await websocket.close(code=close_code)
