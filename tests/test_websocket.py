"""WebSocket 伺服器端身分、回報與連線限流的測試（見 docs/adr/0007、issue #37）。"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.dependencies import get_connection_manager
from app.routers import websocket as ws_router
from app.schemas.boss import BossRecordCreate
from app.services.boss_service import BossService
from app.utils import anonymous_id
from app.utils.identity import Identity
from app.websocket.manager import ConnectionManager
from tests.helpers import make_limited_app

ROOM = "ROOMABCDEF"

app = make_limited_app()
app.include_router(ws_router.router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_services(monkeypatch):
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


def connect(anon: str | None = None, ip: str = "203.0.113.1"):
    headers = {"CF-Connecting-IP": ip}
    if anon:
        headers["cookie"] = f"{anonymous_id.COOKIE_NAME}={anonymous_id.sign(anon)}"
    return client.websocket_connect("/ws/", headers=headers)


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
    with connect(anon, ip) as ws:
        assert ws.receive_json()["code"] == "connection_limited"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == ws_router.CLOSE_CODE_LIMITED


# --- 身分 ---

def test_forged_anonymous_id_in_payload_is_ignored(fake_services):
    anon = str(uuid.uuid4())
    with connect(anon) as ws:
        join(ws)
        assert record(ws, anonymous_id="victim-uuid", anonymous_name="冒充者") == "ok"
    assert fake_services == [Identity("anon", anon)]


def test_recorder_info_comes_from_server_identity():
    db = SimpleNamespace(add=lambda obj: None, commit=lambda: None, refresh=lambda obj: None)
    times = {"base_time": None, "respawn_min_time": None, "respawn_max_time": None}

    def create(identity, **recorder_info):
        payload = BossRecordCreate(room_id=ROOM, channel=1, boss_type_id=1, status="killed",
                                   recorder_info=recorder_info or None)
        import asyncio
        return asyncio.run(BossService._create_boss_record(db, payload, times, identity))

    anon = str(uuid.uuid4())
    forged = create(Identity("anon", anon), anonymous_id="victim-uuid", anonymous_name="小明")
    assert forged.recorder_info == {"anonymous_id": anon, "anonymous_name": "小明"}
    # 匿名者沒設暱稱也記得到身分
    assert create(Identity("anon", anon)).recorder_info == {"anonymous_id": anon, "anonymous_name": None}
    assert create(Identity("none")).recorder_info is None
    user = create(Identity("user", "42"), anonymous_id="victim-uuid")
    assert user.recorder_id == 42 and user.recorder_info is None


def test_authenticate_and_deauthenticate_switch_identity(fake_services, monkeypatch):
    monkeypatch.setattr(ws_router.auth_service, "get_current_user_from_token", lambda token, db: SimpleNamespace(id=42))
    anon = str(uuid.uuid4())
    with connect(anon) as ws:
        join(ws)
        ws.send_json({"type": "authenticate", "token": "access-token"})
        assert record(ws) == "ok"
        ws.send_json({"type": "deauthenticate"})
        assert record(ws) == "ok"
    assert fake_services == [Identity("user", "42"), Identity("anon", anon)]


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
