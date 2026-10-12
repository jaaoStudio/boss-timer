"""匿名身分 cookie 簽章與 /auth/session 發放流程的測試（見 docs/adr/0007）。"""
import uuid

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from jose import jwt

import app.dependencies as deps
from app.config import settings
from app.dependencies import verify_user_session
from app.routers import auth
from app.utils import anonymous_id
from tests.helpers import make_limited_app, set_cookies

app = make_limited_app()
app.include_router(auth.router)


@app.get("/needs-session", dependencies=[Depends(verify_user_session)])
async def needs_session():
    return {"ok": True}


client = TestClient(app)


def init_session(ip: str = "203.0.113.1", cookie: str | None = None, **extra: str):
    set_cookies(client, cookie, signed=False, **extra)
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


def test_logged_in_user_with_expired_access_token_is_not_minted(monkeypatch):
    # 只剩 refresh token 的登入者即將換發 token，不發匿名身分、也不計入發放上限
    monkeypatch.setattr(deps, "ANONYMOUS_ID_MINT_LIMIT", "1/hour")
    for _ in range(3):
        res = init_session(refresh_token="opaque")
        assert res.json() == {"status": "authenticated", "anonymous_user_id": None}
        assert issued_cookie(res) is None
    assert init_session().status_code == 200


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


VALID_TOKEN = jwt.encode({"sub": "42"}, settings.secret_key, algorithm=settings.algorithm)


@pytest.mark.parametrize("cookies, expected", [
    ({"anon": str(uuid.uuid4()), "signed": True}, 200),
    ({"anon": str(uuid.uuid4()), "signed": False}, 200),   # 過渡期：舊 cookie 仍可使用（見 issue #54）
    ({"anon": "made-up-value", "signed": False}, 401),
    ({"access_token": VALID_TOKEN}, 200),
    ({"access_token": "not-a-jwt"}, 401),                   # 只檢查有沒有 token 已不夠，要能解出身分
    ({}, 401),
])
def test_verify_user_session(cookies, expected):
    set_cookies(client, **cookies)
    assert client.get("/needs-session").status_code == expected
