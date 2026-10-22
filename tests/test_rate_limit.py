"""雙層限流（個人額度 + IP 天花板）的行為測試，見 docs/adr/0007。"""
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from starlette.requests import Request as StarletteRequest

from app.config import settings
from app.utils import anonymous_id
from app.dependencies import (
    IP_CEILING_MULTIPLIER,
    get_client_ip,
    rate_limit,
)
from tests.helpers import personal_key, set_cookies


PERSONAL_LIMIT = 2
CEILING = PERSONAL_LIMIT * IP_CEILING_MULTIPLIER

app = FastAPI()


@app.get("/limited", dependencies=[rate_limit(f"{PERSONAL_LIMIT}/minute")])
async def limited_endpoint():
    return {"ok": True}


client = TestClient(app)


def call(ip: str, anon_id: str | None = None, access_token: str | None = None, signed: bool = True) -> int:
    set_cookies(client, anon_id, signed, **({"access_token": access_token} if access_token else {}))
    return client.get("/limited", headers={"CF-Connecting-IP": ip}).status_code


def exhaust_ip_ceiling(ip: str) -> None:
    for _ in range(CEILING):
        call(ip, str(uuid.uuid4()))
    assert call(ip, str(uuid.uuid4())) == 429


def make_request(headers: dict[str, str] | None = None, cookies: str | None = None) -> StarletteRequest:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw_headers.append((b"cookie", cookies.encode()))
    return StarletteRequest({"type": "http", "headers": raw_headers, "client": ("172.70.1.1", 443)})


def test_client_ip_prefers_cf_connecting_ip():
    assert get_client_ip(make_request({"CF-Connecting-IP": "203.0.113.7"})) == "203.0.113.7"


def test_client_ip_falls_back_to_connection_source():
    assert get_client_ip(make_request()) == "172.70.1.1"


def test_personal_key_uses_signed_anonymous_cookie_then_real_ip():
    anon = str(uuid.uuid4())
    signed = anonymous_id.sign(anon)
    assert personal_key(make_request(cookies=f"{anonymous_id.COOKIE_NAME}={signed}")) == f"anon:{anon}"
    assert personal_key(make_request({"CF-Connecting-IP": "203.0.113.7"})) == "ip:203.0.113.7"


def test_forged_or_legacy_cookie_falls_back_to_real_ip():
    # verify() 的各種拒絕情境在 test_anonymous_id.py；這裡只確認接線：不是伺服器簽發的值就用 IP
    headers = {"CF-Connecting-IP": "203.0.113.7"}
    for value in ["made-up", str(uuid.uuid4())]:
        request = make_request(headers, cookies=f"{anonymous_id.COOKIE_NAME}={value}")
        assert personal_key(request) == "ip:203.0.113.7"


def test_ipv4_mapped_ipv6_uses_ipv4_key():
    assert personal_key(make_request({"CF-Connecting-IP": "::ffff:203.0.113.7"})) == "ip:203.0.113.7"


def test_ipv6_key_collapses_to_64_prefix():
    key = personal_key(make_request({"CF-Connecting-IP": "2407:4d00:bc01:14e3:64a0:b1e7:f2a2:e28d"}))
    assert key == "ip:2407:4d00:bc01:14e3::/64"


def test_same_cookie_is_limited_by_personal_quota():
    codes = [call("203.0.113.1", "fixed") for _ in range(PERSONAL_LIMIT + 1)]
    assert codes == [200] * PERSONAL_LIMIT + [429]


def test_rotating_forged_cookie_is_limited_as_one_person():
    # 自己編造的 cookie 不被當成匿名身分，全部算在同一個 IP 的個人額度
    codes = [call("203.0.113.1", str(uuid.uuid4()), signed=False) for _ in range(PERSONAL_LIMIT + 1)]
    assert codes == [200] * PERSONAL_LIMIT + [429]


def test_many_signed_identities_hit_ip_ceiling():
    codes = [call("203.0.113.1", str(uuid.uuid4())) for _ in range(CEILING + 1)]
    assert codes[:CEILING] == [200] * CEILING
    assert codes[CEILING] == 429


def test_shared_ip_players_each_get_full_personal_quota():
    # 大量玩家（例如學校）共用一個 IP，每人用滿自己的額度都不會被擋
    players = [str(uuid.uuid4()) for _ in range(IP_CEILING_MULTIPLIER)]
    codes = [call("203.0.113.1", p) for p in players for _ in range(PERSONAL_LIMIT)]
    assert set(codes) == {200}


def test_different_ips_have_independent_ceilings():
    exhaust_ip_ceiling("203.0.113.1")
    assert call("198.51.100.9", str(uuid.uuid4())) == 200


def test_rotating_ipv6_within_same_64_shares_ceiling():
    codes = [
        call(f"2407:4d00:bc01:14e3::{i:x}", str(uuid.uuid4()))
        for i in range(1, CEILING + 2)
    ]
    assert codes[:CEILING] == [200] * CEILING
    assert codes[CEILING] == 429
    assert call("2407:4d00:bc01:9999::1", str(uuid.uuid4())) == 200


def test_logged_in_user_is_not_blocked_by_exhausted_ip_ceiling():
    exhaust_ip_ceiling("203.0.113.1")
    token = jwt.encode({"sub": "42", "type": "access"}, settings.secret_key, algorithm=settings.algorithm)
    assert call("203.0.113.1", access_token=token) == 200


def test_every_http_route_has_a_route_level_rate_limit():
    # 掛在其他 dependency 裡或改回 decorator，限流就會在拿資料庫鎖之後才檢查（#82）。
    # /health 給 Docker healthcheck 與部署腳本，不限流（被擋會誤判下線）
    from fastapi.routing import APIRoute
    from app.main import app as main_app

    unlimited = [
        route.path for route in main_app.routes
        if isinstance(route, APIRoute) and route.path != "/health"
        and not any(getattr(d.dependency, "__qualname__", "") == "rate_limit.<locals>.check" for d in route.dependencies)
    ]
    assert unlimited == []


def test_rate_limited_request_does_not_take_the_database_lock():
    # 超過限流的請求在拿資料庫鎖、查登入之前就要被擋下（#82）：不然有人狂打 API 時，每個被擋的請求都要先在鎖裡
    # 跑一次查詢，其他人的資料庫工作跟著排隊
    from fastapi import Depends

    from app.database.database import get_db

    db_calls = []
    db_app = FastAPI()

    async def fake_db():
        db_calls.append(True)
        yield None

    db_app.dependency_overrides[get_db] = fake_db

    @db_app.get("/with-db", dependencies=[rate_limit("1/minute")])
    def with_db(db=Depends(get_db)):
        return {"ok": True}

    db_client = TestClient(db_app)
    headers = {"CF-Connecting-IP": "203.0.113.50"}
    assert db_client.get("/with-db", headers=headers).status_code == 200
    assert db_client.get("/with-db", headers=headers).status_code == 429
    assert db_calls == [True]


def test_logged_in_user_with_expired_access_token_is_not_limited_by_the_ip_ceiling():
    # access token 過期時以 refresh token 認出登入者（ADR-0009）。IP 天花板也要以這個登入者計算，
    # 不然同 IP 有人灌爆天花板時，連換發 token 的 /auth/session 都會被擋（ADR-0007：登入者不受同 IP 其他人影響）
    ip = "203.0.113.60"
    exhaust_ip_ceiling(ip)
    refresh = jwt.encode({"sub": "77", "type": "refresh"}, settings.secret_key, algorithm=settings.algorithm)
    set_cookies(client, refresh_token=refresh)
    assert client.get("/limited", headers={"CF-Connecting-IP": ip}).status_code == 200
