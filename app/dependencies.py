# app/dependencies.py
import ipaddress

from fastapi import Depends, WebSocket, status, HTTPException, Request
from fastapi.exceptions import WebSocketException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

from limits import parse, parse_many
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import models
from app.database.database import SessionLocal
from app.websocket.manager import ConnectionManager
from app.services.auth_service import decode_token_user_id, get_current_user, get_current_user_from_token
from app.utils.identity import resolve_identity

# IP 天花板 = 個人額度 × 200（見 docs/adr/0007）。匿名身分有簽章、無法任意編造後，
# 天花板只是最後防線，放寬到能容納學校、行動網路 CGNAT 等大量玩家共用一個 IP
IP_CEILING_MULTIPLIER = 200

# 每個 IP 每小時最多發放幾個新匿名身分（含舊 cookie 換發）：要容納整班學生第一次同時進站；
# 正常使用者 cookie 有效期一年，幾乎不會重新申請
ANONYMOUS_ID_MINT_LIMIT = "100/hour"


def get_client_ip(request: Request) -> str:
    """
    使用者的真實 IP。
    request.client 是 Traefik 轉來的 Cloudflare 節點 IP，真實 IP 在 CF-Connecting-IP；
    Traefik 只接受 Cloudflare 來的連線（cf-only），這個 header 才不會被偽造。
    沒有這個 header（本機開發、直連後端）時退回連線來源。
    """
    return request.headers.get("cf-connecting-ip") or get_remote_address(request)


def get_ip_rate_limit_key(request: Request) -> str:
    """
    以 IP 限流時的 key。IPv6 縮成 /64：一般家用網路會分到整段 /64，
    以單一位址計算的話，每次換位址就是全新的額度。不縮到 /56：行動網路常從共用的大段位址
    替每支手機各配一段 /64，縮得更粗會把不相干的使用者算在一起。
    """
    ip = get_client_ip(request)
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return f"ip:{ip}"
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    if addr.version == 6:
        return f"ip:{ipaddress.ip_network(f'{addr}/64', strict=False)}"
    return f"ip:{addr}"


def get_ip_ceiling_key(request: Request) -> str:
    """
    IP 天花板的 key。登入者無法更換身分，以自己的 user key 計算，不受同 IP 其他人影響
    （天花板遠大於個人額度，實際上永遠先撞個人額度）。
    """
    identity = resolve_identity(request)
    return f"user:{identity.id}" if identity.kind == "user" else get_ip_rate_limit_key(request)


def get_user_identifier(request: Request) -> str:
    """
    個人額度的 key：登入者 user:{id} → 伺服器簽發的匿名身分 anon:{uuid} → 真實 IP。
    編造的 cookie 與舊版無簽章的 cookie 都不算身分，退回 IP。
    """
    identity = resolve_identity(request)
    if identity.kind in ("user", "anon"):
        return f"{identity.kind}:{identity.id}"
    return get_ip_rate_limit_key(request)

limiter = Limiter(key_func=get_user_identifier, key_style="endpoint")


def check_anonymous_id_mint(request: Request) -> None:
    """
    發放新匿名身分前呼叫：以真實 IP 計數，超過 ANONYMOUS_ID_MINT_LIMIT 就回 429。
    不用 rate_limit()：只有真的發放時才計數，已有身分的請求不算。
    """
    if not limiter.enabled:
        return
    item = parse(ANONYMOUS_ID_MINT_LIMIT)
    if not limiter.limiter.hit(item, "anonymous_id_mint", get_ip_rate_limit_key(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Rate limit exceeded: {item}")


def scale_limit(limit_value: str, factor: int) -> str:
    """把 "15/minute;50/day" 的每條上限乘上 factor。"""
    return ";".join(
        f"{item.amount * factor} per {item.multiples} {item.GRANULARITY.name}"
        for item in parse_many(limit_value)
    )


def get_refresh_token_user_key(request: Request) -> str:
    """
    /auth/refresh 的個人額度 key：以 refresh token 裡的使用者計算。呼叫者的 access token 已過期，
    若退回 IP，同一個 IP 上的登入者會共用額度、互相把對方擋到被登出。
    """
    user_id = decode_token_user_id(request.cookies.get("refresh_token"), token_type="refresh")
    return f"user:{user_id}" if user_id else get_user_identifier(request)


def rate_limit(limit_value: str, personal_key_func=None):
    """
    雙層限流（見 docs/adr/0007）：
    - 個人額度：limit_value，以登入身分或伺服器簽發的匿名身分計算（都沒有時以 IP），維持公平；
      編造的 cookie 不算身分，換 cookie 狂打會直接撞到 IP 的個人額度
    - IP 天花板：limit_value × IP_CEILING_MULTIPLIER，以真實 IP（IPv6 以 /64）計算，是最後防線：
      擋同一個 IP 申請大量身分後灌爆；登入者改以自己的身分計算，不受同 IP 其他人影響
    """
    personal = limiter.limit(limit_value, key_func=personal_key_func)
    ceiling = limiter.limit(scale_limit(limit_value, IP_CEILING_MULTIPLIER), key_func=get_ip_ceiling_key)

    def decorator(func):
        return ceiling(personal(func))

    return decorator

# 自定義速率限制超過時的例外處理函式
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )

_connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return _connection_manager


async def get_current_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    驗證當前使用者是否為管理員。
    """
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to perform this action")
    return current_user


async def get_current_user_from_ws(
    websocket: WebSocket,
) -> Optional[models.User]:
    """
    從 WebSocket 連線的 access_token cookie 取得使用者；token 無效、過期或類型不符時回傳 None（匿名）。
    使用短暫的 DB session，不長持連線。
    """
    token = websocket.cookies.get("access_token")
    if not token:
        return None
    with SessionLocal() as db:
        try:
            return get_current_user_from_token(token, db)
        except HTTPException:
            return None
