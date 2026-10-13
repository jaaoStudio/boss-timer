"""匿名身分 cookie 簽章、身分解析與 /auth/session 發放流程的測試（見 docs/adr/0007）。"""
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.requests import Request
from starlette.websockets import WebSocket

import app.dependencies as deps
from app.config import settings
from app.dependencies import get_refresh_token_user_key
from app.routers import auth
from app.utils import anonymous_id
from app.utils import identity as identity_module
from app.utils.identity import Identity, resolve_identity
from tests.helpers import make_limited_app, set_cookies

app = make_limited_app()
app.include_router(auth.router)
client = TestClient(app)


def token(token_type: str, sub: str = "42") -> str:
    return jwt.encode({"sub": sub, "type": token_type}, settings.secret_key, algorithm=settings.algorithm)


def http_request(cookie_header: bytes = b"") -> Request:
    return Request({"type": "http", "headers": [(b"cookie", cookie_header)] if cookie_header else []})


def init_session(ip: str = "203.0.113.1", cookie: str | None = None, **extra: str):
    set_cookies(client, cookie, signed=False, **extra)
    return client.post("/auth/session", headers={"CF-Connecting-IP": ip})


def issued_cookie(response) -> str | None:
    return response.cookies.get(anonymous_id.COOKIE_NAME)


# --- 簽章 ---

def test_sign_and_verify_roundtrip():
    anon = str(uuid.uuid4())
    assert anonymous_id.verify(anonymous_id.sign(anon)) == anon


@pytest.mark.parametrize("value", [None, "", "no-dot", "abc.def", f"{uuid.uuid4()}"])
def test_verify_rejects_unsigned_or_forged(value):
    assert anonymous_id.verify(value) is None


def test_verify_rejects_signature_from_another_id():
    other_signature = anonymous_id.sign(str(uuid.uuid4())).rsplit(".", 1)[1]
    assert anonymous_id.verify(f"{uuid.uuid4()}.{other_signature}") is None


@pytest.mark.parametrize("value", ["a.\xe9", f"{uuid.uuid4()}.{'é' * 43}"])
def test_verify_rejects_non_ascii_without_raising(value):
    # hmac.compare_digest 遇到非 ASCII 會拋 TypeError；格式不符要在比對前就擋下
    assert anonymous_id.verify(value) is None


# --- 身分解析 ---

def test_resolve_identity_kinds():
    signed = anonymous_id.sign(str(uuid.uuid4()))
    assert resolve_identity(http_request(f"access_token={token('access')}".encode())) == Identity("user", "42")
    assert resolve_identity(http_request(f"{anonymous_id.COOKIE_NAME}={signed}".encode())).kind == "anon"
    assert resolve_identity(http_request(f"{anonymous_id.COOKIE_NAME}={uuid.uuid4()}".encode())) == Identity("none")
    assert resolve_identity(http_request()) == Identity("none")


def test_refresh_token_cannot_be_used_as_access_token():
    assert resolve_identity(http_request(f"access_token={token('refresh')}".encode())) == Identity("none")


def test_non_ascii_cookie_resolves_to_none():
    # Starlette 以 latin-1 解碼 header，cookie 值可能含非 ASCII 字元
    assert resolve_identity(http_request(b"anonymous_user_id=a.\xe9")) == Identity("none")


def test_websocket_identity_is_not_cached(monkeypatch):
    # WS 連線中途會切換身分，不可把解析結果留在連線上
    monkeypatch.setattr(identity_module, "_user_exists", lambda db, user_id: True)
    ws = WebSocket({"type": "websocket", "headers": [(b"cookie", f"access_token={token('access')}".encode())]},
                   receive=None, send=None)
    assert resolve_identity(ws) == Identity("user", "42")
    assert getattr(ws.state, "identity", None) is None


def test_refresh_rate_limit_is_keyed_by_refresh_token_user():
    assert get_refresh_token_user_key(http_request(f"refresh_token={token('refresh', '7')}".encode())) == "user:7"
    # 拿 access token 冒充 refresh token：不算，退回一般的個人額度 key
    request = Request({"type": "http", "client": ("203.0.113.9", 0),
                       "headers": [(b"cookie", f"refresh_token={token('access', '7')}".encode())]})
    assert get_refresh_token_user_key(request) == "ip:203.0.113.9"


# --- /auth/session ---

def test_new_visitor_gets_signed_httponly_cookie():
    res = init_session()
    assert res.status_code == 200 and res.json()["status"] == "anonymous_session_created"
    anon = res.json()["anonymous_user_id"]
    assert anonymous_id.verify(issued_cookie(res)) == anon
    assert "httponly" in res.headers["set-cookie"].lower()


def test_signed_cookie_is_reused_without_new_cookie():
    anon = str(uuid.uuid4())
    res = init_session(cookie=anonymous_id.sign(anon))
    assert res.json() == {"status": "session_ok", "anonymous_user_id": anon}
    assert issued_cookie(res) is None


@pytest.mark.parametrize("cookie", ["made-up-value", str(uuid.uuid4())])
def test_forged_or_legacy_cookie_gets_a_fresh_identity(cookie):
    # 舊的無簽章 cookie 不換發成同一個 UUID：匿名 UUID 會廣播給房間所有人，無法確認送來的人是本人
    res = init_session(cookie=cookie)
    assert res.json()["status"] == "anonymous_session_created"
    assert res.json()["anonymous_user_id"] != cookie
    assert anonymous_id.verify(issued_cookie(res)) == res.json()["anonymous_user_id"]


def test_logged_in_user_with_expired_access_token_is_not_minted(monkeypatch):
    # 只剩有效 refresh token 的登入者即將換發 token，不發匿名身分、也不計入發放上限
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "1/hour")
    monkeypatch.setattr(auth.auth_service, "verify_refresh_token", lambda db, t: 42 if t == "valid" else None)
    for _ in range(3):
        res = init_session(refresh_token="valid")
        assert res.json() == {"status": "authenticated", "anonymous_user_id": None}
        assert issued_cookie(res) is None
    assert init_session().status_code == 200


def test_revoked_or_invalid_refresh_token_still_gets_anonymous_identity(monkeypatch):
    # 被撤銷（例如在其他裝置登入）或無效的 refresh token 不能讓人一直拿不到匿名身分
    monkeypatch.setattr(auth.auth_service, "verify_refresh_token", lambda db, t: None)
    res = init_session(refresh_token="revoked")
    assert res.json()["status"] == "anonymous_session_created"
    assert anonymous_id.verify(issued_cookie(res)) == res.json()["anonymous_user_id"]


def test_rejected_refresh_token_cookie_is_deleted(monkeypatch):
    monkeypatch.setattr(auth.auth_service, "verify_refresh_token", lambda db, t: None)
    set_cookies(client, refresh_token="revoked")
    res = client.post("/auth/refresh", headers={"CF-Connecting-IP": "203.0.113.1"})
    assert res.status_code == 401
    assert 'refresh_token=""' in res.headers["set-cookie"] and "max-age=0" in res.headers["set-cookie"].lower()


def test_mint_limit_per_ip_does_not_affect_existing_identities(monkeypatch):
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "3/hour")
    assert [init_session().status_code for _ in range(4)] == [200, 200, 200, 429]
    # 已有合法 cookie 的使用者不需發放，不受影響；其他 IP 也不受影響
    assert init_session(cookie=anonymous_id.sign(str(uuid.uuid4()))).status_code == 200
    assert init_session(ip="198.51.100.9").status_code == 200


def test_anonymous_websocket_handshake_does_not_touch_the_database(monkeypatch):
    def no_db():
        raise AssertionError("anonymous handshake opened a DB session")

    monkeypatch.setattr(identity_module, "SessionLocal", no_db)
    signed = anonymous_id.sign(str(uuid.uuid4()))
    ws = WebSocket({"type": "websocket", "headers": [(b"cookie", f"{anonymous_id.COOKIE_NAME}={signed}".encode())]},
                   receive=None, send=None)
    assert resolve_identity(ws).kind == "anon"
