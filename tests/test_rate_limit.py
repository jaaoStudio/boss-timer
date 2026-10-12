"""雙層限流（個人額度 + IP 天花板）的行為測試，見 docs/adr/0007。"""
import uuid

from fastapi import Request
from fastapi.testclient import TestClient
from jose import jwt
from starlette.requests import Request as StarletteRequest

from app.config import settings
from app.utils import anonymous_id
from app.dependencies import (
    IP_CEILING_MULTIPLIER,
    get_client_ip,
    get_user_identifier,
    rate_limit,
    scale_limit,
)
from tests.helpers import make_limited_app, set_cookies

PERSONAL_LIMIT = 2
CEILING = PERSONAL_LIMIT * IP_CEILING_MULTIPLIER

app = make_limited_app()


@app.get("/limited")
@rate_limit(f"{PERSONAL_LIMIT}/minute")
async def limited_endpoint(request: Request):
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


def test_scale_limit_multiplies_every_limit():
    assert scale_limit("15/minute;50/day", 50) == "750 per 1 minute;2500 per 1 day"


def test_client_ip_prefers_cf_connecting_ip():
    assert get_client_ip(make_request({"CF-Connecting-IP": "203.0.113.7"})) == "203.0.113.7"


def test_client_ip_falls_back_to_connection_source():
    assert get_client_ip(make_request()) == "172.70.1.1"


def test_personal_key_uses_signed_anonymous_cookie_then_real_ip():
    signed = anonymous_id.sign("abc")
    assert get_user_identifier(make_request(cookies=f"{anonymous_id.COOKIE_NAME}={signed}")) == "anon:abc"
    assert get_user_identifier(make_request({"CF-Connecting-IP": "203.0.113.7"})) == "ip:203.0.113.7"


def test_forged_or_legacy_cookie_falls_back_to_real_ip():
    # verify() 的各種拒絕情境在 test_anonymous_id.py；這裡只確認接線：不是伺服器簽發的值就用 IP
    headers = {"CF-Connecting-IP": "203.0.113.7"}
    for value in ["made-up", str(uuid.uuid4())]:
        request = make_request(headers, cookies=f"{anonymous_id.COOKIE_NAME}={value}")
        assert get_user_identifier(request) == "ip:203.0.113.7"


def test_ipv4_mapped_ipv6_uses_ipv4_key():
    assert get_user_identifier(make_request({"CF-Connecting-IP": "::ffff:203.0.113.7"})) == "ip:203.0.113.7"


def test_ipv6_key_collapses_to_64_prefix():
    key = get_user_identifier(make_request({"CF-Connecting-IP": "2407:4d00:bc01:14e3:64a0:b1e7:f2a2:e28d"}))
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
