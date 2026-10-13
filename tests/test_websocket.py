"""WebSocket 伺服器端身分、回報與連線限流的測試（見 docs/adr/0007、issue #37）。"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from app.dependencies import get_connection_manager
from app.routers import websocket as ws_router
from app.schemas.boss import BossRecordCreate
from app.services.boss_service import BossService
from app.config import settings
from app.utils import anonymous_id
from app.utils.identity import Identity
from app.websocket.manager import ConnectionManager
from tests.helpers import make_limited_app

ROOM = "ROOMABCDEF"

app = make_limited_app()
app.include_router(ws_router.router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def recorded_identities(monkeypatch):
    """不連資料庫：房間一律存在；回報只記下伺服器端身分，並廣播 ok 讓測試知道已處理。"""
    manager = ConnectionManager()
    app.dependency_overrides[get_connection_manager] = lambda: manager
    monkeypatch.setattr(ws_router.room_service, "get_room_by_id", lambda db, room_id: True)
    monkeypatch.setattr(ws_router.room_service, "update_room_last_active", lambda db, room_id: None)
    monkeypatch.setattr(ws_router.room_service, "get_room_state", lambda db, room_id: {"type": "room_state"})

    recorded: list[Identity] = []

    async def fake_record(db, record, identity, manager):
        recorded.append(identity)
        await manager.broadcast_to_room(record.room_id, {"type": "ok"})

    monkeypatch.setattr(ws_router.boss_service.BossService, "record_boss_from_websocket", staticmethod(fake_record))
    yield recorded
    app.dependency_overrides.clear()


def connect(anon: str | None = None, ip: str = "203.0.113.1", **cookies: str):
    if anon:
        cookies[anonymous_id.COOKIE_NAME] = anonymous_id.sign(anon)
    headers = {"CF-Connecting-IP": ip}
    if cookies:
        headers["cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return client.websocket_connect("/ws/", headers=headers)


def access_token(user_id: str = "42") -> str:
    return jwt.encode({"sub": user_id, "type": "access"}, settings.secret_key, algorithm=settings.algorithm)


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
    with connect(anon, ip) as ws:
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
    ({"refresh_token": "valid"}, False, 42, Identity("user", "42")),
    # 使用者已刪除：access token 仍在效期內也不算（refresh token 已隨使用者刪除）
    ({"access_token": access_token()}, False, None, Identity("none")),
    ({"refresh_token": "revoked"}, False, None, Identity("none")),
])
def test_handshake_identity(recorded_identities, monkeypatch, cookies, user_exists, refresh_user, expected):
    monkeypatch.setattr(ws_router, "_user_exists", lambda db, user_id: user_exists)
    monkeypatch.setattr(ws_router.auth_service, "verify_refresh_token", lambda db, token: refresh_user)
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
        return asyncio.run(BossService._create_boss_record(db, payload, times, identity))

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


# --- 用戶端斷線偵測（ADR-0008）---

def test_ping_is_answered_with_pong():
    with connect(str(uuid.uuid4())) as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
