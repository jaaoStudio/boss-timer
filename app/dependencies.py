# app/dependencies.py
import ipaddress
from functools import lru_cache

from fastapi import Depends, status, HTTPException, Request
from fastapi.responses import JSONResponse

from limits import parse_many
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import HTTPConnection

from app.database import models
from app.websocket.manager import ConnectionManager
from app.services.auth_service import decode_token, decode_token_user_id, get_current_user
from app.utils.identity import Identity, resolve_identity

# IP 天花板 = 個人額度 × 200（見 docs/adr/0007）。匿名身分有簽章、無法任意編造後，
# 天花板只是最後防線，放寬到能容納學校、行動網路 CGNAT 等大量玩家共用一個 IP
IP_CEILING_MULTIPLIER = 200

# 每個 IP 每小時最多發放幾個新匿名身分：要容納整班學生第一次同時進站；
# 正常使用者 cookie 有效期一年，幾乎不會重新申請
ANONYMOUS_ID_MINT_LIMIT = "100/hour"


def get_client_ip(request: HTTPConnection) -> str:
    """
    使用者的真實 IP。
    request.client 是 Traefik 轉來的 Cloudflare 節點 IP，真實 IP 在 CF-Connecting-IP；
    Traefik 只接受 Cloudflare 來的連線（cf-only），這個 header 才不會被偽造。
    沒有這個 header（本機開發、直連後端）時退回連線來源。
    """
    return request.headers.get("cf-connecting-ip") or get_remote_address(request)


def get_ip_rate_limit_key(request: HTTPConnection) -> str:
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


def personal_limit_key(identity: Identity, conn: HTTPConnection) -> str:
    """個人額度的 key：登入者 user:{id} → 伺服器簽發的匿名身分 anon:{uuid} → 真實 IP。"""
    if identity.kind in ("user", "anon"):
        return f"{identity.kind}:{identity.id}"
    return get_ip_rate_limit_key(conn)


def ceiling_limit_key(identity: Identity, conn: HTTPConnection) -> str:
    """
    IP 天花板的 key。登入者無法更換身分，以自己的 user key 計算，不受同 IP 其他人影響
    （天花板遠大於個人額度，實際上永遠先撞個人額度）。
    """
    return f"user:{identity.id}" if identity.kind == "user" else get_ip_rate_limit_key(conn)


def limit_keys(identity: Identity, conn: HTTPConnection) -> tuple[str, str]:
    """(個人額度 key, IP 天花板 key)。"""
    return personal_limit_key(identity, conn), ceiling_limit_key(identity, conn)


def get_ip_ceiling_key(request: Request) -> str:
    """slowapi 的 key_func：IP 天花板，見 ceiling_limit_key。"""
    return ceiling_limit_key(resolve_identity(request), request)


def get_user_identifier(request: Request) -> str:
    """slowapi 的預設 key_func：個人額度，見 personal_limit_key。"""
    return personal_limit_key(resolve_identity(request), request)

limiter = Limiter(key_func=get_user_identifier, key_style="endpoint")


@lru_cache(maxsize=None)
def _limit_items(limit_value: str, factor: int = 1) -> tuple:
    """解析 "30/minute;1000/day" 並把每條上限乘上 factor；設定值固定，只解析一次。"""
    return tuple(type(item)(item.amount * factor, item.multiples) for item in parse_many(limit_value))


def _hit_all(limit_value: str, scope: str, key: str, factor: int = 1) -> bool:
    """
    依序計數每條上限，任一條超過就回傳 False（之後的不再計數）。
    被後面的時間窗擋下時，前面的時間窗已經計數（與 slowapi 行為一致）。
    """
    if not limiter.enabled:
        return True
    return all(limiter.limiter.hit(item, scope, key) for item in _limit_items(limit_value, factor))


def check_dual_limit(limit_value: str, scope: str, keys: tuple[str, str]) -> bool:
    """
    給無法用 rate_limit() decorator 的地方（WebSocket 訊息、握手）使用的雙層限流：
    個人額度 limit_value，IP 天花板為其 IP_CEILING_MULTIPLIER 倍；keys 為 limit_keys() 的結果。
    與 decorator 的差異：個人額度被擋時不計入天花板（decorator 由 slowapi 依序計數，結果相同）。
    """
    personal_key, ceiling_key = keys
    if not _hit_all(limit_value, f"{scope}:personal", personal_key):
        return False
    # 登入者兩個 key 相同，天花板永遠不會先觸發，不必再計數
    return ceiling_key == personal_key or _hit_all(limit_value, f"{scope}:ceiling", ceiling_key, IP_CEILING_MULTIPLIER)


def anonymous_id_mint_allowed(request: Request) -> bool:
    """
    發放新匿名身分前呼叫：以真實 IP 計數，超過 ANONYMOUS_ID_MINT_LIMIT 回傳 False。
    不用 rate_limit()：只有真的發放時才計數，已有身分的請求不算。
    """
    return _hit_all(ANONYMOUS_ID_MINT_LIMIT, "anonymous_id_mint", get_ip_rate_limit_key(request))


def scale_limit(limit_value: str, factor: int) -> str:
    """把 "15/minute;50/day" 的每條上限乘上 factor（給 slowapi decorator 用的字串版本）。"""
    return ";".join(
        f"{item.amount} per {item.multiples} {item.GRANULARITY.name}" for item in _limit_items(limit_value, factor)
    )


def get_login_user_key(request: Request) -> str:
    """
    /auth/session、/auth/refresh 的個人額度 key：access token 的使用者 → 這個 refresh token（jti）→ 一般規則。
    呼叫者的 access token 常已過期，若退回匿名身分或 IP，同一個 IP 上的登入者會共用額度、互相擋到。
    只解開 refresh token、不查資料庫，所以以 token 本身計算、不以裡面的使用者：拿到舊的或被撤銷的 refresh token
    重送，只會用掉那個 token 的額度，不會擋到使用者目前的登入。
    """
    if resolve_identity(request).kind != "user":
        payload = decode_token(request.cookies.get("refresh_token"), token_type="refresh")
        if payload and payload.get("jti"):
            return f"refresh:{payload['jti']}"
    return get_user_identifier(request)


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

# 自定義速率限制超過時的例外處理函式。前端以 detail 開頭的 "Rate limit exceeded" 辨認限流器的 429（handlingErrors.ts），勿改這個開頭
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
