"""雙層限流（個人額度 + IP 天花板）的行為測試，見 docs/adr/0007。"""
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request as StarletteRequest

from app.config import settings
from app.dependencies import (
    IP_CEILING_MULTIPLIER,
    get_client_ip,
    get_user_identifier,
    limiter,
    rate_limit,
    rate_limit_exceeded_handler,
    scale_limit,
)

PERSONAL_LIMIT = 2
CEILING = PERSONAL_LIMIT * IP_CEILING_MULTIPLIER

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.get("/limited")
@rate_limit(f"{PERSONAL_LIMIT}/minute")
async def limited_endpoint(request: Request):
    return {"ok": True}


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()


def call(ip: str, anon_id: str | None = None, access_token: str | None = None) -> int:
    client.cookies.clear()
    if anon_id:
        client.cookies.set("anonymous_user_id", anon_id)
    if access_token:
        client.cookies.set("access_token", access_token)
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


def test_scale_limit_multiplies_every_limit():
    assert scale_limit("15/minute;50/day", 50) == "750 per 1 minute;2500 per 1 day"


def test_client_ip_prefers_cf_connecting_ip():
    assert get_client_ip(make_request({"CF-Connecting-IP": "203.0.113.7"})) == "203.0.113.7"


def test_client_ip_falls_back_to_connection_source():
    assert get_client_ip(make_request()) == "172.70.1.1"


def test_personal_key_uses_anonymous_cookie_then_real_ip():
    assert get_user_identifier(make_request(cookies="anonymous_user_id=abc")) == "anon:abc"
    assert get_user_identifier(make_request({"CF-Connecting-IP": "203.0.113.7"})) == "ip:203.0.113.7"


def test_ipv6_key_collapses_to_64_prefix():
    key = get_user_identifier(make_request({"CF-Connecting-IP": "2407:4d00:bc01:14e3:64a0:b1e7:f2a2:e28d"}))
    assert key == "ip:2407:4d00:bc01:14e3::/64"


def test_same_cookie_is_limited_by_personal_quota():
    codes = [call("203.0.113.1", "fixed") for _ in range(PERSONAL_LIMIT + 1)]
    assert codes == [200] * PERSONAL_LIMIT + [429]


def test_rotating_cookie_hits_ip_ceiling():
    codes = [call("203.0.113.1", str(uuid.uuid4())) for _ in range(CEILING + 1)]
    assert codes[:CEILING] == [200] * CEILING
    assert codes[CEILING] == 429


def test_shared_ip_players_each_get_full_personal_quota():
    # 學校 50 人共用一個 IP，每人用滿自己的額度都不會被擋
    players = [f"student-{i}" for i in range(IP_CEILING_MULTIPLIER)]
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
    token = jwt.encode({"sub": "42"}, settings.secret_key, algorithm=settings.algorithm)
    assert call("203.0.113.1", access_token=token) == 200
