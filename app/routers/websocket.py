# app/routers/websocket.py
import json
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.database.database import SessionLocal, db_lock
from app.services import room_service, boss_service
from app.dependencies import IP_CEILING_MULTIPLIER, check_dual_limit, get_connection_manager, limit_keys
from app.utils.identity import Identity, has_login_cookies, resolve_identity
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


Handler = Callable[[WebSocket, dict, Optional[str], ConnectionManager, Connection], Awaitable[None]]

# 處理訊息的 handler 在 event loop 上執行，ConnectionManager 只在 event loop 上操作；查資料庫的部分放進
# threadpool（run_in_threadpool），各自開 session，不卡住所有連線（ADR-0010）


def _load_room_state(room_id: str) -> Optional[dict]:
    with SessionLocal() as db:
        if not room_service.get_room_by_id(db, room_id):
            return None
        room_service.update_room_last_active(db, room_id)
        return room_service.get_room_state(db, room_id)


def _record_boss(record: BossRecordCreate, identity: Identity, manager: ConnectionManager) -> None:
    with SessionLocal() as db:
        boss_service.BossService.record_boss(
            db, record, identity,
            broadcast=lambda message: manager.broadcast_to_room_from_thread(record.room_id, message),
        )


async def _handle_join_room(websocket: WebSocket, payload: dict, room_id: Optional[str], manager: ConnectionManager, conn: Connection) -> None:
    # 讀房間狀態與訂閱都在資料庫鎖裡：別人的回報要等訂閱好才寫得進去，不會在兩者之間廣播而漏接（ADR-0010）。
    # 取得初始狀態成功後才訂閱：出錯時（例如資料庫故障）連線保留，但不留在房間裡卻沒有初始狀態
    async with db_lock():
        initial_state = await run_in_threadpool(_load_room_state, room_id)
        if initial_state is None:
            manager.send(websocket, {"type": "error", "code": "room_not_found", "message": "Room not found"})
            return
        manager.subscribe_to_room(websocket, room_id)
        manager.send(websocket, initial_state)
    await manager.broadcast_user_count(room_id)


async def _handle_leave_room(websocket: WebSocket, payload: dict, room_id: Optional[str], manager: ConnectionManager, conn: Connection) -> None:
    manager.unsubscribe_from_room(websocket)
    await manager.broadcast_user_count(room_id)


async def _handle_record_boss(websocket: WebSocket, payload: dict, room_id: Optional[str], manager: ConnectionManager, conn: Connection) -> None:
    current_room = manager.socket_to_room.get(websocket)
    if not current_room or current_room != room_id:
        manager.send(websocket, {"type": "error", "code": "record_rejected", "message": "You are not in this room"})
        return
    if not check_dual_limit(RECORD_BOSS_LIMIT, "ws_record_boss", conn.limit_keys):
        manager.send(websocket, {"type": "error", "code": "rate_limited", "message": "Rate limit exceeded. Please slow down."})
        return
    try:
        record_create = BossRecordCreate(**payload)
        async with db_lock():
            await run_in_threadpool(_record_boss, record_create, conn.identity, manager)
    except Exception as e:
        logging.error(f"Error processing record_boss message: {e}", exc_info=True)
        manager.send(websocket, {"type": "error", "code": "record_rejected", "message": str(e)})


_HANDLERS: dict[str, Handler] = {
    "join_room": _handle_join_room,
    "leave_room": _handle_leave_room,
    "record_boss": _handle_record_boss,
}


async def handle_message(websocket: WebSocket, message: dict, manager: ConnectionManager, conn: Connection) -> None:
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

    await handler(websocket, payload, room_id, manager, conn)


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


# 握手查資料庫失敗的完整錯誤堆疊，一分鐘最多記一次（#76）：資料庫故障期間大量分頁一直退避重連，log 會被同樣的堆疊洗版
HANDSHAKE_TRACEBACK_INTERVAL_SECONDS = 60
_last_handshake_traceback: Optional[float] = None   # 還沒記過；time.monotonic() 從開機算起，不能用 0 當起點


def _log_handshake_failure(error: Exception) -> None:
    global _last_handshake_traceback
    now = time.monotonic()
    full = _last_handshake_traceback is None or now - _last_handshake_traceback >= HANDSHAKE_TRACEBACK_INTERVAL_SECONDS
    if full:
        _last_handshake_traceback = now
        logging.error("WebSocket handshake identity lookup failed", exc_info=error)
    else:
        # 只記一行也帶上錯誤類型與訊息：同一分鐘內換成別的錯誤時才分得出來
        logging.error("WebSocket handshake identity lookup failed: %r", error)


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: ConnectionManager = Depends(get_connection_manager)
):
    # 有登入 cookie 時會查資料庫，放到 threadpool，不卡住其他連線
    try:
        if has_login_cookies(websocket.cookies):
            async with db_lock():
                identity = await run_in_threadpool(resolve_identity, websocket)
        else:
            identity = resolve_identity(websocket)   # 匿名握手不查資料庫
    except Exception as error:
        # 查資料庫失敗（暫時故障、連線池逾時，#61）：記錄後拒絕這次握手（還沒 accept，uvicorn 回 HTTP 403，
        # 前端看到 1006），前端照一般斷線退避重連，資料庫恢復後就照完整判斷連上。勿退回較低的身分：
        # 身分在握手時固定，前端看到的身分沒變就不會重連，會一直以錯的身分回報
        _log_handshake_failure(error)
        await websocket.close()
        return
    conn = Connection(identity, limit_keys(identity, websocket))
    # 先檢查握手頻率、再檢查同時連線數，勿對調：對調的話被連線數擋下的嘗試不會計入握手頻率，
    # 開著超過上限分頁的人可以不受頻率限制地一直重試
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
                await handle_message(websocket, message, manager, conn)
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
