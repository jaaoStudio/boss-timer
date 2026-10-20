"""WebSocket 伺服器端身分、回報與連線限流的測試（見 docs/adr/0007、issue #37）。"""
import asyncio
import json
import uuid
from contextlib import contextmanager, suppress
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from app.dependencies import get_connection_manager
from app.routers import websocket as ws_router
from app.schemas.boss import BossRecordCreate
from app.services.boss_service import BossService
from app.config import settings
from app.utils import anonymous_id
from app.utils import identity as identity_module
from app.utils.identity import Identity
from app.websocket import manager as manager_module
from app.websocket.manager import HEARTBEAT_INTERVAL_SECONDS, HEARTBEAT_TIMEOUT_SECONDS, HELLO_MESSAGE, ConnectionManager

ROOM = "ROOMABCDEF"

app = FastAPI()
app.include_router(ws_router.router)
client = TestClient(app)


def off_event_loop() -> None:
    """在 threadpool 執行緒裡沒有執行中的 event loop；在 event loop 上呼叫就讓測試失敗"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise AssertionError("在 event loop 上查了同步的資料庫")


@pytest.fixture(autouse=True)
def recorded_identities(monkeypatch):
    """不連資料庫：房間一律存在；回報只記下伺服器端身分，並廣播 ok 讓測試知道已處理。"""
    manager = ConnectionManager()
    app.dependency_overrides[get_connection_manager] = lambda: manager
    # 假的資料庫操作都檢查不在 event loop 上執行（ADR-0010）：在 event loop 上查同步的資料庫會卡住所有連線
    monkeypatch.setattr(ws_router.room_service, "get_room_by_id", lambda db, room_id: off_event_loop() or True)
    monkeypatch.setattr(ws_router.room_service, "update_room_last_active", lambda db, room_id: off_event_loop())
    monkeypatch.setattr(ws_router.room_service, "get_room_state", lambda db, room_id: off_event_loop() or {"type": "room_state"})

    recorded: list[Identity] = []

    def fake_record(db, record, identity, broadcast):
        off_event_loop()
        recorded.append(identity)
        broadcast({"type": "ok"})   # 回報成功時廣播給房間（從 threadpool 回到 event loop）

    monkeypatch.setattr(ws_router.boss_service.BossService, "record_boss", staticmethod(fake_record))
    # 在 with client 內，所有連線共用同一個 portal（同一個 event loop），與正式環境相同；
    # 否則每條連線各自一個 loop，廣播跨 loop 放進送出佇列不是 thread-safe
    with client:
        yield recorded
    app.dependency_overrides.clear()


def open_socket(anon: str | None = None, ip: str = "203.0.113.1", **cookies: str):
    if anon:
        cookies[anonymous_id.COOKIE_NAME] = anonymous_id.sign(anon)
    headers = {"CF-Connecting-IP": ip}
    if cookies:
        headers["cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return client.websocket_connect("/ws/", headers=headers)


@contextmanager
def connect(anon: str | None = None, ip: str = "203.0.113.1", **cookies: str):
    """建立被接受的連線，並讀掉伺服器的第一則訊息 hello。"""
    with open_socket(anon, ip, **cookies) as ws:
        assert ws.receive_json()["type"] == "hello"
        yield ws


def access_token(user_id: str = "42", token_type: str = "access") -> str:
    return jwt.encode({"sub": user_id, "type": token_type}, settings.secret_key, algorithm=settings.algorithm)


def join(ws) -> None:
    ws.send_json({"type": "join_room", "payload": {"room_id": ROOM}})
    assert ws.receive_json()["type"] == "room_state"
    assert ws.receive_json()["type"] == "user_count_update"


def record(ws, **recorder_info) -> str:
    """送一筆回報，回傳伺服器的回應類型（ok / error 的 code）。"""
    ws.send_json({"type": "record_boss", "payload": {
        "room_id": ROOM, "channel": 1, "boss_type_id": 1, "status": "killed",
        "recorder_info": recorder_info or None,
    }})
    msg = ws.receive_json()
    return msg["type"] if msg["type"] == "ok" else msg["code"]


def assert_rejected(anon: str | None = None, ip: str = "203.0.113.1") -> None:
    # 只以 close code 拒絕、不先送訊息：前端收到訊息會重置重連次數
    with open_socket(anon, ip) as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == ws_router.CLOSE_CODE_LIMITED and exc.value.reason == "connection_limited"


# --- 身分 ---

def test_forged_anonymous_id_in_payload_is_ignored(recorded_identities):
    anon = str(uuid.uuid4())
    with connect(anon) as ws:
        join(ws)
        assert record(ws, anonymous_id="victim-uuid", anonymous_name="冒充者") == "ok"
    assert recorded_identities == [Identity("anon", anon)]


@pytest.mark.parametrize("cookies, user_exists, refresh_user, expected", [
    ({"access_token": access_token()}, True, None, Identity("user", "42")),
    # 背景分頁在 access token 過期後重連：改以 refresh token 認出登入者
    ({"refresh_token": access_token(token_type="refresh")}, True, 42, Identity("user", "42")),
    # 使用者已刪除：access token 仍在效期內也不算（refresh token 已隨使用者刪除）
    ({"access_token": access_token()}, False, None, Identity("none")),
    ({"refresh_token": access_token(token_type="refresh")}, True, None, Identity("none")),
])
def test_handshake_identity(recorded_identities, monkeypatch, cookies, user_exists, refresh_user, expected):
    monkeypatch.setattr(identity_module, "_get_user",
                        lambda db, user_id: SimpleNamespace(id=int(user_id)) if user_exists else None)
    monkeypatch.setattr(identity_module.auth_service, "verify_refresh_token", lambda db, token: refresh_user)
    with connect(**cookies) as ws:
        join(ws)
        assert record(ws) == "ok"
    assert recorded_identities == [expected]


def test_recorder_info_comes_from_server_identity():
    db = SimpleNamespace(add=lambda obj: None, commit=lambda: None, refresh=lambda obj: None)
    times = {"base_time": None, "respawn_min_time": None, "respawn_max_time": None}

    def create(identity, **recorder_info):
        payload = BossRecordCreate(room_id=ROOM, channel=1, boss_type_id=1, status="killed",
                                   recorder_info=recorder_info or None)
        return BossService._create_boss_record(db, payload, times, identity)

    anon = str(uuid.uuid4())
    forged = create(Identity("anon", anon), anonymous_id="victim-uuid", anonymous_name="小明")
    assert forged.recorder_info == {"anonymous_id": anon, "anonymous_name": "小明"}
    # 匿名者沒設暱稱也記得到身分
    assert create(Identity("anon", anon)).recorder_info == {"anonymous_id": anon, "anonymous_name": None}
    assert create(Identity("none")).recorder_info is None
    user = create(Identity("user", "42"), anonymous_id="victim-uuid")
    assert user.recorder_id == 42 and user.recorder_info is None


def test_identity_is_fixed_at_handshake(recorded_identities):
    # 登入 / 登出時前端重新連線；舊版前端仍可能送 authenticate / deauthenticate，伺服器忽略
    anon = str(uuid.uuid4())
    with connect(anon) as ws:
        join(ws)
        ws.send_json({"type": "authenticate", "token": "access-token"})
        assert record(ws) == "ok"
        ws.send_json({"type": "deauthenticate"})
        assert record(ws) == "ok"
    assert recorded_identities == [Identity("anon", anon)] * 2


# --- 回報限流 ---

def test_record_limit_is_not_reset_by_reconnecting(monkeypatch):
    monkeypatch.setattr(ws_router, "RECORD_BOSS_LIMIT", "3/minute")
    anon = str(uuid.uuid4())
    with connect(anon) as ws:
        join(ws)
        assert [record(ws), record(ws)] == ["ok", "ok"]
    with connect(anon) as ws:
        join(ws)
        assert [record(ws), record(ws)] == ["ok", "rate_limited"]


def test_record_limit_is_per_identity(monkeypatch):
    monkeypatch.setattr(ws_router, "RECORD_BOSS_LIMIT", "1/minute")
    with connect(str(uuid.uuid4())) as a, connect(str(uuid.uuid4())) as b:
        join(a)
        join(b)
        assert a.receive_json()["type"] == "user_count_update"   # b 加入時廣播給 a
        assert record(a) == "ok"
        assert b.receive_json()["type"] == "ok"   # a 的回報也會廣播給同房間的 b
        assert record(b) == "ok"
        assert a.receive_json()["type"] == "ok"


# --- 連線限流 ---

def test_concurrent_connections_per_identity(monkeypatch):
    monkeypatch.setattr(ws_router, "MAX_CONNECTIONS", 2)
    anon = str(uuid.uuid4())
    with connect(anon), connect(anon):
        assert_rejected(anon)
        with connect(str(uuid.uuid4())):   # 其他人不受影響
            pass
    with connect(anon):                    # 斷線後名額會釋放
        pass


def test_no_identity_connections_do_not_share_count_with_ip_ceiling(monkeypatch):
    # 沒有身分時個人與天花板的 key 都是 IP，兩者分開計數：匿名者佔用的天花板不會吃掉無身分者的個人上限
    monkeypatch.setattr(ws_router, "MAX_CONNECTIONS", 1)
    monkeypatch.setattr(ws_router, "IP_CEILING_MULTIPLIER", 3)
    with connect(str(uuid.uuid4())), connect():
        assert_rejected()   # 無身分者的個人上限 1 條已用完


def test_concurrent_connections_ip_ceiling(monkeypatch):
    monkeypatch.setattr(ws_router, "MAX_CONNECTIONS", 1)
    monkeypatch.setattr(ws_router, "IP_CEILING_MULTIPLIER", 2)
    with connect(str(uuid.uuid4())), connect(str(uuid.uuid4())):
        assert_rejected(str(uuid.uuid4()))
        with connect(str(uuid.uuid4()), ip="198.51.100.9"):   # 其他 IP 不受影響
            pass


def test_handshake_rate_limit(monkeypatch):
    monkeypatch.setattr(ws_router, "HANDSHAKE_LIMIT", "2/hour")
    anon = str(uuid.uuid4())
    for _ in range(2):
        with connect(anon):
            pass
    assert_rejected(anon)


# --- 伺服器心跳（ADR-0008）---

def test_hello_announces_heartbeat_parameters():
    with open_socket(str(uuid.uuid4())) as ws:
        assert ws.receive_json() == {
            "type": "hello",
            "ping_interval": HEARTBEAT_INTERVAL_SECONDS,
            "ping_timeout": HEARTBEAT_TIMEOUT_SECONDS,
        }


def test_heartbeat_reaches_every_connection():
    manager = app.dependency_overrides[get_connection_manager]()
    broadcast = manager.broadcast_to_all

    async def one_beat():
        beat = asyncio.Event()

        async def broadcast_once(message):
            await broadcast(message)
            beat.set()

        manager.broadcast_to_all = broadcast_once
        task = asyncio.create_task(manager.run_heartbeat(interval=0))
        await beat.wait()
        task.cancel()   # 心跳迴圈下一次 sleep 時取消，只送一輪
        with suppress(asyncio.CancelledError):
            await task

    with connect(str(uuid.uuid4())) as first, connect(str(uuid.uuid4())) as second:
        client.portal.call(one_beat)   # 在伺服器的 event loop 上執行
        for ws in (first, second):
            assert ws.receive_json() == {"type": "heartbeat"}
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}   # 只有一輪心跳


class FakeSocket:
    def __init__(self, send=None):
        self.sent: list[dict] = []
        self.closed = False
        self._send = send

    async def accept(self) -> None:
        pass

    async def send_text(self, text: str) -> None:
        if self._send:
            await self._send()
        self.sent.append(json.loads(text))

    async def close(self) -> None:
        self.closed = True


async def until(condition) -> None:
    while not condition():
        await asyncio.sleep(0)


def test_stuck_connection_does_not_hold_up_others():
    """送出佇列（ADR-0008）：廣播不等送出，一條收不下的連線不影響其他連線。"""
    async def scenario():
        manager = ConnectionManager()
        stuck, healthy = FakeSocket(send=asyncio.Event().wait), FakeSocket()
        for ws in (stuck, healthy):
            await manager.connect(ws)

        await asyncio.wait_for(manager.broadcast_to_all({"type": "heartbeat"}), 1)
        await asyncio.wait_for(until(lambda: len(healthy.sent) == 2), 1)

        assert healthy.sent == [HELLO_MESSAGE, {"type": "heartbeat"}]
        assert stuck.sent == []
        for ws in (stuck, healthy):
            manager.disconnect(ws)

    asyncio.run(scenario())


def test_send_failure_closes_connection_and_leaves_cleanup_to_the_endpoint():
    """送不出去就關閉連線，但不在 manager 裡清除，否則 endpoint 的 finally 找不到房間、不會更新房間人數。"""
    async def gone():
        raise WebSocketDisconnect(code=1006)

    async def scenario():
        manager = ConnectionManager()
        dead = FakeSocket(send=gone)
        await manager.connect(dead)
        manager.subscribe_to_room(dead, ROOM)

        await asyncio.wait_for(until(lambda: dead.closed), 1)

        assert manager.socket_to_room[dead] == ROOM
        manager.send(dead, {"type": "ok"})   # 寫出 task 已結束：直接丟棄、不拋例外
        assert dead.sent == []
        manager.disconnect(dead)

    asyncio.run(scenario())


def test_stalled_send_closes_connection(monkeypatch):
    """同一則訊息送太久送不出去就關閉（對應 engine.io 的 pingTimeout），佇列不會無限累積。"""
    monkeypatch.setattr(manager_module, "SEND_STALL_SECONDS", 0.05)

    async def scenario():
        manager = ConnectionManager()
        stalled = FakeSocket(send=asyncio.Event().wait)
        await manager.connect(stalled)

        await asyncio.wait_for(until(lambda: stalled.closed), 1)

        assert stalled not in manager._outboxes
        manager.send(stalled, {"type": "ok"})
        assert stalled not in manager._outboxes   # 不再累積：之後的訊息直接丟棄
        manager.disconnect(stalled)

    asyncio.run(scenario())


def test_slow_but_progressing_connection_is_not_closed(monkeypatch):
    """逾時只算單一則訊息：每則都在時限內送出的慢連線，總時間超過時限也不會被關閉。"""
    monkeypatch.setattr(manager_module, "SEND_STALL_SECONDS", 0.5)

    async def scenario():
        manager = ConnectionManager()
        slow = FakeSocket(send=lambda: asyncio.sleep(0.15))
        await manager.connect(slow)
        for _ in range(4):
            manager.send(slow, {"type": "ok"})

        await asyncio.wait_for(until(lambda: len(slow.sent) == 5), 5)   # 共約 0.75 秒，超過單則時限

        assert not slow.closed
        manager.disconnect(slow)

    asyncio.run(scenario())


@pytest.mark.parametrize("raw", [
    "not json", "[]", '{"type": "join_room", "payload": null}', '{"type": [], "payload": {}}', "[" * 100_000,
])
def test_malformed_message_closes_the_connection(raw):
    """照 engine.io：封包解析失敗才關閉連線，不留下前端以為還連著的殭屍連線。"""
    with connect(str(uuid.uuid4())) as ws:
        ws.send_text(raw)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1007


def test_binary_frame_closes_the_connection():
    with connect(str(uuid.uuid4())) as ws:
        ws.send_bytes(b"\x00")
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1007


def test_unexpected_error_closes_the_connection(monkeypatch):
    """非預期錯誤結束 endpoint 時關閉連線（1011）：uvicorn 不會自己關閉，前端會以為還連著。"""
    async def broken(websocket):
        await websocket.receive_text()
        raise ValueError("unexpected")

    monkeypatch.setattr(ws_router, "_receive_message", broken)
    with connect(str(uuid.uuid4())) as ws:
        ws.send_json({"type": "ping"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1011


def test_handler_error_keeps_the_connection(monkeypatch):
    """照 Socket.IO：單則訊息處理出錯不關閉連線，否則資料庫故障時前端會每秒重連一次。"""
    def db_down(db, room_id):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(ws_router.room_service, "get_room_state", db_down)
    manager = app.dependency_overrides[get_connection_manager]()
    with connect(str(uuid.uuid4())) as ws:
        ws.send_json({"type": "join_room", "payload": {"room_id": ROOM}})
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        assert manager.get_room_user_count(ROOM) == 0   # 沒有初始狀態就不留在房間裡


def test_ping_from_old_frontend_is_answered_with_pong():
    with connect(str(uuid.uuid4())) as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_handshake_database_failure_is_logged_and_rejected(monkeypatch, caplog):
    # 握手查資料庫失敗（#61）：記錄 error log 後拒絕這次連線，前端照一般斷線退避重連，資料庫恢復後照完整判斷連上。
    # 不可退回較低的身分：身分在握手時固定，前端看到的身分沒變就不會重連，會一直以錯的身分回報
    from sqlalchemy.exc import OperationalError

    def broken_session():
        raise OperationalError("SELECT 1", {}, Exception("database is down"))

    monkeypatch.setattr(identity_module, "SessionLocal", broken_session)
    with pytest.raises(WebSocketDisconnect):
        with open_socket(access_token=access_token()) as ws:
            ws.receive_json()
    assert "handshake identity lookup failed" in caplog.text


def test_handshake_failure_logs_full_traceback_at_most_once_a_minute(monkeypatch, caplog):
    # 資料庫故障期間大量分頁一直退避重連（#76）：完整的錯誤堆疊一分鐘只記一次，其餘一行，log 不被洗版
    from sqlalchemy.exc import OperationalError

    def broken_session():
        raise OperationalError("SELECT 1", {}, Exception("database is down"))

    monkeypatch.setattr(identity_module, "SessionLocal", broken_session)
    monkeypatch.setattr(ws_router, "_last_handshake_traceback", None)
    for _ in range(3):
        with pytest.raises(WebSocketDisconnect):
            with open_socket(access_token=access_token()) as ws:
                ws.receive_json()
    failures = [r for r in caplog.records if "handshake identity lookup failed" in r.getMessage()]
    assert len(failures) == 3
    assert sum(1 for r in failures if r.exc_info) == 1
    # 只記一行的也要看得出是什麼錯誤：同一分鐘內換成別的錯誤時才分得出來
    assert all("OperationalError" in r.getMessage() for r in failures if not r.exc_info)


def test_first_handshake_failure_after_boot_logs_full_traceback(monkeypatch, caplog):
    # time.monotonic() 從開機算起：剛開機不到一分鐘、還沒記過時，第一次失敗也要記完整堆疊
    from sqlalchemy.exc import OperationalError

    def broken_session():
        raise OperationalError("SELECT 1", {}, Exception("database is down"))

    monkeypatch.setattr(identity_module, "SessionLocal", broken_session)
    monkeypatch.setattr(ws_router, "_last_handshake_traceback", None)   # 還沒記過（模組載入時的值）
    monkeypatch.setattr(ws_router.time, "monotonic", lambda: 30.0)
    with pytest.raises(WebSocketDisconnect):
        with open_socket(access_token=access_token()) as ws:
            ws.receive_json()
    assert any(r.exc_info for r in caplog.records if "handshake identity lookup failed" in r.getMessage())


def test_join_room_does_not_miss_a_report_made_while_loading_room_state(monkeypatch):
    # 讀房間狀態（threadpool）與訂閱房間（event loop）之間，別人的回報廣播出去的話，加入的人兩邊都收不到。
    # 加入房間在資料庫鎖裡讀完狀態並訂閱好（ADR-0010），回報要等鎖放開才寫得進去，加入的人一定收得到
    import threading
    import time

    loading = threading.Event()

    def slow_room_state(db, room_id):
        off_event_loop()
        loading.set()   # 加入的人已拿到鎖、開始讀房間狀態
        time.sleep(0.2)
        return {"type": "room_state"}

    with connect(str(uuid.uuid4())) as reporter, connect(str(uuid.uuid4())) as joiner:
        join(reporter)
        monkeypatch.setattr(ws_router.room_service, "get_room_state", slow_room_state)
        joiner.send_json({"type": "join_room", "payload": {"room_id": ROOM}})
        assert loading.wait(5)   # 確定加入的人先拿到鎖，回報才會排在它後面
        reporter.send_json({"type": "record_boss", "payload": {
            "room_id": ROOM, "channel": 1, "boss_type_id": 1, "status": "killed", "recorder_info": None,
        }})
        while reporter.receive_json()["type"] != "ok":
            pass
        # 回報已廣播給當時在房間裡的所有人；之後的 pong 一定排在它後面
        joiner.send_json({"type": "ping"})
        received = []
        while not received or received[-1] != "pong":
            received.append(joiner.receive_json()["type"])
        assert "ok" in received, received


def test_handshake_gives_up_waiting_for_the_database_lock(monkeypatch, caplog):
    # 資料庫故障時，鎖前面的工作每個要卡 5～10 秒。握手等鎖要有上限，等不到就拒絕（前端照一般斷線退避重連）；
    # 不設上限的話，前端 20 秒放棄重連後，被放棄的握手仍在排隊，佇列越來越長
    import threading

    import anyio

    from app.database.database import db_lock

    monkeypatch.setattr(ws_router, "HANDSHAKE_LOCK_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(identity_module, "_get_user", lambda db, user_id: SimpleNamespace(id=int(user_id)))
    held, release = threading.Event(), threading.Event()

    async def hold_lock():
        async with db_lock():
            held.set()
            while not release.is_set():
                await anyio.sleep(0.01)

    holder = client.portal.start_task_soon(hold_lock)
    assert held.wait(5)   # 確定鎖被佔住才開始握手
    timer = threading.Timer(1, release.set)   # 沒有上限時，握手等到鎖放開就會連上
    timer.start()
    try:
        with pytest.raises(WebSocketDisconnect):
            with open_socket(access_token=access_token()) as ws:
                ws.receive_json()
    finally:
        release.set()
        timer.cancel()
        holder.result()
    # 等不到鎖是排隊太久（例如部署後的重連潮），記 warning，不和資料庫故障的 error 混在一起
    waits = [r for r in caplog.records if "waited too long for the database lock" in r.getMessage()]
    assert [r.levelname for r in waits] == ["WARNING"]
    assert "handshake identity lookup failed" not in caplog.text
