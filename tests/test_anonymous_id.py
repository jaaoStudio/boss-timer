"""匿名身分 cookie 簽章、身分解析與 /auth/session 發放流程的測試（見 docs/adr/0007）。"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.requests import Request
from starlette.websockets import WebSocket

import app.dependencies as deps
from app.config import settings
from app.database import models
from app.dependencies import get_login_user_key
from app.routers import auth
from app.utils import anonymous_id
from app.utils import identity as identity_module
from app.utils.identity import Identity, resolve_identity
from tests.helpers import make_limited_app, set_cookies

app = make_limited_app()
app.include_router(auth.router)
client = TestClient(app)


def token(token_type: str, sub: str = "42", jti: str = "j") -> str:
    return jwt.encode({"sub": sub, "type": token_type, "jti": jti}, settings.secret_key, algorithm=settings.algorithm)


VALID_REFRESH = token("refresh", "42")
REVOKED_REFRESH = token("refresh", "99")


def http_request(cookie_header: bytes = b"") -> Request:
    return Request({"type": "http", "headers": [(b"cookie", cookie_header)] if cookie_header else []})


def init_session(ip: str = "203.0.113.1", cookie: str | None = None, **extra: str):
    set_cookies(client, cookie, signed=False, **extra)
    return client.post("/auth/session", headers={"CF-Connecting-IP": ip})


def issued_cookie(response) -> str | None:
    return response.cookies.get(anonymous_id.COOKIE_NAME)


def deleted_cookies(response) -> set[str]:
    return {header.split("=", 1)[0] for header in response.headers.get_list("set-cookie")
            if "max-age=0" in header.lower()}


@pytest.fixture
def login(monkeypatch):
    """模擬資料庫：existing 裡的使用者存在；只有 VALID_REFRESH 未被撤銷（對應使用者 42）。"""
    def setup(existing=(42,), refresh_user=42):
        monkeypatch.setattr(identity_module, "_get_user", lambda db, user_id: models.User(
            id=int(user_id), google_id="g", email="a@example.com", display_name="小明", preferences={},
            created_at=datetime.now(timezone.utc), is_admin=False) if int(user_id) in existing else None)
        monkeypatch.setattr(identity_module.auth_service, "verify_refresh_token",
                            lambda db, t: refresh_user if t == VALID_REFRESH else None)
    return setup


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


def test_websocket_identity_is_not_cached(login):
    # WS 的身分由 endpoint 存在該連線的 Connection，resolve_identity 不在 websocket.state 快取
    login()
    ws = WebSocket({"type": "websocket", "headers": [(b"cookie", f"access_token={token('access')}".encode())]},
                   receive=None, send=None)
    assert resolve_identity(ws) == Identity("user", "42")
    assert getattr(ws.state, "identity", None) is None


def test_login_rate_limit_is_keyed_by_login_user():
    # access token 過期時以 refresh token 計算，不退回 IP（同 IP 的人不會互相擋到）
    assert get_login_user_key(http_request(f"refresh_token={token('refresh', '7', jti='current')}".encode())) == "refresh:current"
    # 以 token 本身計算：重送舊的或被撤銷的 refresh token，用不到同一個使用者目前登入的額度
    assert get_login_user_key(http_request(f"refresh_token={token('refresh', '7', jti='revoked')}".encode())) == "refresh:revoked"
    both = f"access_token={token('access', '42')}; refresh_token={token('refresh', '7')}".encode()
    assert get_login_user_key(http_request(both)) == "user:42"
    # 拿 access token 冒充 refresh token：不算，退回一般的個人額度 key
    request = Request({"type": "http", "client": ("203.0.113.9", 0),
                       "headers": [(b"cookie", f"refresh_token={token('access', '7')}".encode())]})
    assert get_login_user_key(request) == "ip:203.0.113.9"


# --- /auth/session ---

def test_new_visitor_gets_signed_httponly_cookie():
    res = init_session()
    assert res.status_code == 200 and res.json()["status"] == "anonymous"
    anon = res.json()["anonymous_user_id"]
    assert anonymous_id.verify(issued_cookie(res)) == anon
    assert "httponly" in res.headers["set-cookie"].lower()


def test_signed_cookie_is_reused_without_new_cookie():
    anon = str(uuid.uuid4())
    res = init_session(cookie=anonymous_id.sign(anon))
    assert res.json() == {"status": "anonymous", "user": None, "anonymous_user_id": anon}
    assert issued_cookie(res) is None


@pytest.mark.parametrize("cookie", ["made-up-value", str(uuid.uuid4())])
def test_forged_or_legacy_cookie_gets_a_fresh_identity(cookie):
    # 舊的無簽章 cookie 不換發成同一個 UUID：匿名 UUID 會廣播給房間所有人，無法確認送來的人是本人
    res = init_session(cookie=cookie)
    assert res.json()["status"] == "anonymous"
    assert res.json()["anonymous_user_id"] != cookie
    assert anonymous_id.verify(issued_cookie(res)) == res.json()["anonymous_user_id"]


def test_valid_access_token_returns_the_user(login):
    login()
    res = init_session(access_token=token("access"))
    assert res.json()["status"] == "authenticated" and res.json()["user"]["id"] == 42
    assert res.headers.get("set-cookie") is None   # 不換發、不發匿名身分


def test_expired_access_token_is_renewed_with_refresh_token(monkeypatch, login):
    # 只剩有效 refresh token 的登入者：換發 access token，不發匿名身分、也不計入發放上限
    login()
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "1/hour")
    for _ in range(3):
        res = init_session(refresh_token=VALID_REFRESH)
        assert res.json()["status"] == "authenticated" and res.json()["user"]["id"] == 42
        assert identity_module.auth_service.decode_token_user_id(res.cookies.get("access_token")) == "42"
        assert issued_cookie(res) is None
    assert init_session().status_code == 200


@pytest.mark.parametrize("cookies", [
    {"refresh_token": REVOKED_REFRESH},   # 被撤銷（例如在其他裝置登入）或過期
    {"access_token": token("access"), "refresh_token": REVOKED_REFRESH},   # 使用者已刪除
    {"access_token": "garbage"},
    {"refresh_token": "garbage"},
])
def test_stale_login_is_cleared_and_becomes_anonymous(login, cookies):
    login(existing=())
    res = init_session(**cookies)
    assert res.json()["status"] == "anonymous"
    assert anonymous_id.verify(issued_cookie(res)) == res.json()["anonymous_user_id"]
    assert {"access_token", "refresh_token"} <= deleted_cookies(res)


@pytest.mark.parametrize("cookies", [
    {"refresh_token": REVOKED_REFRESH},
    {"access_token": "garbage", "refresh_token": "garbage"},
])
def test_stale_login_keeps_existing_anonymous_identity(login, cookies):
    login(existing=())
    anon = str(uuid.uuid4())
    res = init_session(cookie=anonymous_id.sign(anon), **cookies)
    assert res.json() == {"status": "anonymous", "user": None, "anonymous_user_id": anon}
    assert {"access_token", "refresh_token"} <= deleted_cookies(res)


@pytest.mark.parametrize("cookies", [
    {"refresh_token": REVOKED_REFRESH},
    {"access_token": "garbage"},
])
def test_stale_login_over_mint_limit_is_anonymous_without_identity(monkeypatch, login, cookies):
    # 舊登入失效又撞到發放上限：照樣清掉舊登入，回匿名、暫時沒有身分
    login(existing=())
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "1/hour")
    assert init_session().status_code == 200
    res = init_session(**cookies)
    assert res.status_code == 200
    assert res.json() == {"status": "anonymous", "user": None, "anonymous_user_id": None}
    assert issued_cookie(res) is None
    assert {"access_token", "refresh_token"} <= deleted_cookies(res)


def test_rejected_refresh_token_cookie_is_deleted(monkeypatch):
    monkeypatch.setattr(auth.auth_service, "verify_refresh_token", lambda db, t: None)
    set_cookies(client, refresh_token="revoked")
    res = client.post("/auth/refresh", headers={"CF-Connecting-IP": "203.0.113.1"})
    assert res.status_code == 401
    assert 'refresh_token=""' in res.headers["set-cookie"] and "max-age=0" in res.headers["set-cookie"].lower()


def test_mint_limit_per_ip_does_not_affect_existing_identities(monkeypatch):
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "3/hour")
    assert [issued_cookie(init_session()) is not None for _ in range(4)] == [True, True, True, False]
    # 撞到上限不回 429：拿不到身分，回匿名、暫時沒有身分（以 IP 限流）
    res = init_session()
    assert res.status_code == 200
    assert res.json() == {"status": "anonymous", "user": None, "anonymous_user_id": None}
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
