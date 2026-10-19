"""匿名身分 cookie 簽章、身分解析與 /auth/session 發放流程的測試（見 docs/adr/0007）。"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from fastapi import HTTPException, Response
from starlette.requests import Request
from starlette.websockets import WebSocket

import app.dependencies as deps
from app.config import settings
from app.database import models
from app.dependencies import get_user_identifier
from app.routers import auth, feedback
from app.services.feedback_service import FeedbackRateLimited, FeedbackService
from app.utils import anonymous_id
from app.utils import identity as identity_module
from app.utils.identity import Identity, resolve_identity
from tests.helpers import make_limited_app, set_cookies

app = make_limited_app()
app.include_router(auth.router)
app.include_router(feedback.router)
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


def test_personal_rate_limit_uses_refresh_token_user_when_access_token_is_invalid():
    # access token 過期時以 refresh token 裡的使用者計算，不退回 IP（同 IP 的人不會互相擋到）
    assert get_user_identifier(http_request(f"refresh_token={token('refresh', '7', jti='current')}".encode())) == "user:7"
    # 以使用者而不是 token 本身計算：舊的或被撤銷的 token 不會各拿一份額度
    assert get_user_identifier(http_request(f"refresh_token={token('refresh', '7', jti='revoked')}".encode())) == "user:7"
    both = f"access_token={token('access', '42')}; refresh_token={token('refresh', '7')}".encode()
    assert get_user_identifier(http_request(both)) == "user:42"
    # 拿 access token 冒充 refresh token：不算，退回一般的個人額度 key
    request = Request({"type": "http", "client": ("203.0.113.9", 0),
                       "headers": [(b"cookie", f"refresh_token={token('access', '7')}".encode())]})
    assert get_user_identifier(request) == "ip:203.0.113.9"


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


# --- 需要登入的 API（get_current_user / get_optional_user）---

def get_me(**cookies: str):
    set_cookies(client, **cookies)
    return client.get("/auth/me", headers={"CF-Connecting-IP": "203.0.113.2"})


def test_login_required_api_renews_expired_access_token(login):
    # access token 過期、refresh token 有效：伺服器在這次回應換發，請求照常成功（ADR-0009「使用中途遇到 401」）
    login()
    res = get_me(refresh_token=VALID_REFRESH)
    assert res.status_code == 200 and res.json()["id"] == 42
    assert identity_module.auth_service.decode_token_user_id(res.cookies.get("access_token")) == "42"


def test_login_required_api_does_not_renew_valid_access_token(login):
    login()
    res = get_me(access_token=token("access"))
    assert res.status_code == 200 and res.headers.get("set-cookie") is None


@pytest.mark.parametrize("cookies", [
    {},
    {"refresh_token": REVOKED_REFRESH},   # 被撤銷（例如在其他裝置登入）：401 就是登入失效
    {"access_token": "garbage"},
])
def test_login_required_api_rejects_lost_login(login, cookies):
    login()
    assert get_me(**cookies).status_code == 401


def test_optional_user_renews_expired_access_token(login):
    # 例如回饋清單：access token 過期時仍以登入者身分載入，並換發
    login()
    response = Response()
    user = deps.get_optional_user(http_request(f"refresh_token={VALID_REFRESH}".encode()), response, db=None)
    assert user is not None and user.id == 42
    assert "access_token=" in response.headers.get("set-cookie", "")
    assert deps.get_optional_user(http_request(), Response(), db=None) is None   # 沒有登入 cookie：匿名


def test_optional_user_rejects_lost_login(login):
    # 帶著登入 cookie 但登入已失效：401，前端照登入失效處理，不悄悄當成匿名
    login()
    with pytest.raises(HTTPException) as exc:
        deps.get_optional_user(http_request(f"refresh_token={REVOKED_REFRESH}".encode()), Response(), db=None)
    assert exc.value.status_code == 401


# --- 前端依賴的錯誤約定（ADR-0009「使用中途遇到 401」）---

def test_invalid_google_credential_is_400_not_401(monkeypatch):
    # 401 在整個後端只代表登入失效，前端遇到 401 會當成登入失效處理
    monkeypatch.setattr(auth.auth_service, "verify_google_token", lambda credential: None)
    set_cookies(client)
    res = client.post("/auth/google", json={"credential": "bad"}, headers={"CF-Connecting-IP": "203.0.113.3"})
    assert res.status_code == 400


def test_feedback_daily_limit_429_carries_code(monkeypatch, login):
    # 前端全域只略過帶這個 code 的 429，由回饋頁提示每日上限；改了這個約定，使用者只會看到「操作太頻繁」
    login()

    def over_limit(db, user_id, payload):
        raise FeedbackRateLimited("每日上限")

    monkeypatch.setattr(FeedbackService, "create_feedback", staticmethod(over_limit))
    set_cookies(client, access_token=token("access"))
    res = client.post("/feedback/", json={"type": "bug", "title": "t"}, headers={"CF-Connecting-IP": "203.0.113.4"})
    assert res.status_code == 429
    assert res.json()["detail"]["code"] == "feedback_daily_limit"


# --- 登入者資料與握手的容錯（#65、#61）---

def test_user_without_display_name_does_not_break_session(monkeypatch):
    # Google 沒有回傳名稱時 display_name 是 NULL：所有回傳使用者的端點都不能因此 500（開頁會跳錯誤頁）
    monkeypatch.setattr(identity_module, "_get_user", lambda db, user_id: models.User(
        id=42, google_id="g", email="a@example.com", display_name=None, preferences={},
        created_at=datetime.now(timezone.utc), is_admin=False))
    res = init_session(access_token=token("access"))
    assert res.status_code == 200
    assert res.json()["user"]["display_name"] is None


def test_google_login_creates_user_without_display_name(monkeypatch):
    # Google 沒有回傳名稱：建立使用者與登入回應都不能因為 display_name 是 NULL 而失敗
    monkeypatch.setattr(auth.auth_service, "verify_google_token", lambda credential: {"sub": "g-new", "email": "n@example.com"})
    monkeypatch.setattr(auth.auth_service, "get_user_by_google_id", lambda db, google_id: None)
    monkeypatch.setattr(auth.auth_service, "create_user", lambda db, user_data: models.User(
        id=7, google_id=user_data.google_id, email=user_data.email, display_name=user_data.display_name,
        preferences={}, created_at=datetime.now(timezone.utc), is_admin=False))
    monkeypatch.setattr(auth.auth_service, "save_refresh_token", lambda db, user_id, refresh_token: None)
    set_cookies(client)
    res = client.post("/auth/google", json={"credential": "ok"}, headers={"CF-Connecting-IP": "203.0.113.5"})
    assert res.status_code == 200
    assert res.json()["user"]["display_name"] is None


def test_public_user_without_display_name():
    # 回報紀錄的記錄者、回饋的建立者
    from app.schemas.auth import PublicUser
    user = models.User(id=7, google_id="g", email="n@example.com", display_name=None)
    assert PublicUser.model_validate(user).display_name is None


# --- 登入時同步 Google 的名稱與頭像（#77）---

class _NoopSession:
    def commit(self):
        pass

    def refresh(self, obj):
        pass


def _google_login(monkeypatch, payload, existing=None):
    """以 Google 登入，回傳伺服器拿去建立或更新的資料。"""
    seen = {}
    monkeypatch.setattr(auth.auth_service, "verify_google_token", lambda credential: payload)
    monkeypatch.setattr(auth.auth_service, "get_user_by_google_id", lambda db, google_id: existing)

    def create_user(db, user_data):
        seen["created"] = user_data
        return models.User(id=7, google_id=user_data.google_id, email=user_data.email, display_name=user_data.display_name,
                           avatar_url=user_data.avatar_url, preferences={}, created_at=datetime.now(timezone.utc), is_admin=False)

    def update_login(db, user, display_name=None, avatar_url=None):
        seen["updated"] = (display_name, avatar_url)
        return user

    monkeypatch.setattr(auth.auth_service, "create_user", create_user)
    monkeypatch.setattr(auth.auth_service, "update_user_last_login", update_login)
    monkeypatch.setattr(auth.auth_service, "save_refresh_token", lambda db, user_id, refresh_token: None)
    set_cookies(client)
    res = client.post("/auth/google", json={"credential": "ok"}, headers={"CF-Connecting-IP": "203.0.113.6"})
    assert res.status_code == 200
    return seen


def test_existing_user_login_passes_google_name_and_picture(monkeypatch):
    # 第一次登入時沒有名稱、之後 Google 有了，或改了名字 / 頭像：登入時更新
    existing = models.User(id=7, google_id="g", email="n@example.com", display_name=None, avatar_url=None,
                           preferences={}, created_at=datetime.now(timezone.utc), is_admin=False)
    seen = _google_login(monkeypatch, {"sub": "g", "email": "n@example.com", "name": "小明", "picture": "https://p"}, existing)
    assert seen["updated"] == ("小明", "https://p")


def test_google_name_is_truncated_to_column_length(monkeypatch):
    # users.display_name 是 String(100)：超過時建立使用者會丟 DataError、回 500，這個人永遠登入不了
    seen = _google_login(monkeypatch, {"sub": "g-long", "email": "l@example.com", "name": "名" * 150})
    assert len(seen["created"].display_name) == 100


def test_update_last_login_keeps_values_google_did_not_send():
    user = models.User(id=7, google_id="g", email="n@example.com", display_name="小明", avatar_url="https://old")
    auth.auth_service.update_user_last_login(_NoopSession(), user, display_name=None, avatar_url="https://new")
    assert user.display_name == "小明" and user.avatar_url == "https://new"


def test_blank_google_name_does_not_overwrite_or_store_blank(monkeypatch):
    # 只有空白的名稱等於沒有名稱：不蓋掉原本的名稱，建立時存成 NULL
    existing = models.User(id=7, google_id="g", email="n@example.com", display_name="小明", avatar_url=None,
                           preferences={}, created_at=datetime.now(timezone.utc), is_admin=False)
    seen = _google_login(monkeypatch, {"sub": "g", "email": "n@example.com", "name": "   "}, existing)
    assert seen["updated"][0] is None
    seen = _google_login(monkeypatch, {"sub": "g-new", "email": "b@example.com", "name": "  名字  "})
    assert seen["created"].display_name == "名字"
