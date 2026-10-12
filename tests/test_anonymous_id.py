"""匿名身分 cookie 簽章與 /auth/session 發放流程的測試（見 docs/adr/0007）。"""
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

import app.dependencies as deps
from app.dependencies import limiter, rate_limit_exceeded_handler, verify_user_session
from app.routers import auth
from app.utils import anonymous_id

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.include_router(auth.router)


@app.get("/needs-session", dependencies=[Depends(verify_user_session)])
async def needs_session():
    return {"ok": True}


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()


def init_session(ip: str = "203.0.113.1", cookie: str | None = None):
    client.cookies.clear()
    if cookie:
        client.cookies.set(anonymous_id.COOKIE_NAME, cookie)
    return client.post("/auth/session", headers={"CF-Connecting-IP": ip})


def issued_cookie(response) -> str | None:
    return response.cookies.get(anonymous_id.COOKIE_NAME)


def test_sign_and_verify_roundtrip():
    anon = str(uuid.uuid4())
    assert anonymous_id.verify(anonymous_id.sign(anon)) == anon


@pytest.mark.parametrize("value", [None, "", "no-dot", "abc.def", f"{uuid.uuid4()}"])
def test_verify_rejects_unsigned_or_forged(value):
    assert anonymous_id.verify(value) is None


def test_verify_rejects_signature_from_another_id():
    other_signature = anonymous_id.sign(str(uuid.uuid4())).rsplit(".", 1)[1]
    assert anonymous_id.verify(f"{uuid.uuid4()}.{other_signature}") is None


def test_legacy_id_accepts_only_canonical_uuid4():
    legacy = str(uuid.uuid4())
    assert anonymous_id.legacy_id(legacy) == legacy
    assert anonymous_id.legacy_id(legacy.upper()) is None
    assert anonymous_id.legacy_id(str(uuid.uuid1())) is None
    assert anonymous_id.legacy_id("hello") is None


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


def test_legacy_cookie_is_migrated_to_signed_same_uuid():
    legacy = str(uuid.uuid4())
    res = init_session(cookie=legacy)
    assert res.json() == {"status": "anonymous_session_migrated", "anonymous_user_id": legacy}
    assert anonymous_id.verify(issued_cookie(res)) == legacy


def test_forged_cookie_gets_a_fresh_identity():
    res = init_session(cookie="made-up-value")
    assert res.json()["status"] == "anonymous_session_created"
    assert res.json()["anonymous_user_id"] != "made-up-value"


def test_mint_limit_per_ip_does_not_affect_existing_identities(monkeypatch):
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "3/hour")
    assert [init_session().status_code for _ in range(4)] == [200, 200, 200, 429]
    # 已有合法 cookie 的使用者不需發放，不受影響；其他 IP 也不受影響
    assert init_session(cookie=anonymous_id.sign(str(uuid.uuid4()))).status_code == 200
    assert init_session(ip="198.51.100.9").status_code == 200


def test_legacy_migration_counts_toward_mint_limit(monkeypatch):
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "1/hour")
    assert init_session(cookie=str(uuid.uuid4())).status_code == 200
    assert init_session(cookie=str(uuid.uuid4())).status_code == 429


@pytest.mark.parametrize("cookie, expected", [
    (anonymous_id.sign(str(uuid.uuid4())), 200),
    (str(uuid.uuid4()), 200),   # 過渡期：舊 cookie 仍可使用，避免開著的分頁被踢出房間
    ("made-up-value", 401),
    (None, 401),
])
def test_verify_user_session(cookie, expected):
    client.cookies.clear()
    if cookie:
        client.cookies.set(anonymous_id.COOKIE_NAME, cookie)
    assert client.get("/needs-session").status_code == expected
