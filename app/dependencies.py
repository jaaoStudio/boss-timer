# app/dependencies.py
import ipaddress
from typing import Optional
from functools import lru_cache

from fastapi import Depends, status, HTTPException, Request, Response

from limits import parse_many
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from starlette.requests import HTTPConnection

from app.database import models
from app.websocket.manager import ConnectionManager
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.auth_service import decode_token_user_id
from app.utils.identity import Identity, has_login_cookies, resolve_identity, resolve_login
from app.utils.login_cookies import set_access_token_cookie

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
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "127.0.0.1")


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
    """HTTP API 的 IP 天花板 key，見 ceiling_limit_key。"""
    return ceiling_limit_key(resolve_identity(request), request)


def get_user_identifier(request: Request) -> str:
    """
    HTTP API 的個人額度 key，見 personal_limit_key。access token 無效時改以 refresh token 裡的使用者計算：
    需要登入的 API 與 /auth/session 在 access token 過期時照樣以登入者處理並換發（ADR-0009），
    若退回匿名身分或 IP，同一個 IP 上的登入者會共用額度、互相擋到（ADR-0007）。
    只解開 refresh token、不查資料庫：以使用者而不是 token 本身（jti）計算，舊的或已撤銷的 token 才不會各拿一份額度
    （每次登入都會產生新的 jti，輪流使用就能繞過每日上限）
    """
    identity = resolve_identity(request)
    if identity.kind != "user":
        if refresh_user := decode_token_user_id(request.cookies.get("refresh_token"), token_type="refresh"):
            return f"user:{refresh_user}"
    return personal_limit_key(identity, request)

# 計數器存在記憶體，每次部署歸零（ADR-0007）
limit_storage = MemoryStorage()
_rate_limiter = FixedWindowRateLimiter(limit_storage)


@lru_cache(maxsize=None)
def _limit_items(limit_value: str, factor: int = 1) -> tuple:
    """解析 "30/minute;1000/day" 並把每條上限乘上 factor；設定值固定，只解析一次。"""
    return tuple(type(item)(item.amount * factor, item.multiples) for item in parse_many(limit_value))


def _hit_all(limit_value: str, scope: str, key: str, factor: int = 1) -> bool:
    """
    依序計數每條上限，任一條超過就回傳 False（之後的不再計數）。
    被後面的時間窗擋下時，前面的時間窗已經計數。
    """
    return all(_rate_limiter.hit(item, scope, key) for item in _limit_items(limit_value, factor))


def check_dual_limit(limit_value: str, scope: str, keys: tuple[str, str]) -> bool:
    """
    雙層限流（HTTP 的 rate_limit()、WebSocket 訊息與握手共用）：個人額度 limit_value，IP 天花板為其
    IP_CEILING_MULTIPLIER 倍；keys 為 (個人額度 key, IP 天花板 key)。個人額度被擋時不計入天花板。
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


def rate_limit(limit_value: str):
    """
    HTTP API 的雙層限流（見 docs/adr/0007），以路由層級的 dependency 掛上：
    `@router.get("/", dependencies=[rate_limit("15/minute;50/day")])`
    - 個人額度：limit_value，以登入身分或伺服器簽發的匿名身分計算（都沒有時以 IP），維持公平；
      編造的 cookie 不算身分，換 cookie 狂打會直接撞到 IP 的個人額度
    - IP 天花板：limit_value × IP_CEILING_MULTIPLIER，以真實 IP（IPv6 以 /64）計算，是最後防線：
      擋同一個 IP 申請大量身分後灌爆；登入者改以自己的身分計算，不受同 IP 其他人影響
    FastAPI 先解析路由層級的 dependency：超過限流的請求不會拿資料庫鎖、查登入（#82，ADR-0010）。
    勿改回包在端點外面的 decorator：那要等所有 dependency 解析完才檢查。每個端點各自計數
    """
    async def check(request: Request) -> None:
        endpoint = request.scope["endpoint"]
        keys = (get_user_identifier(request), get_ip_ceiling_key(request))
        if not check_dual_limit(limit_value, f"{endpoint.__module__}.{endpoint.__qualname__}", keys):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Rate limit exceeded: {limit_value}")

    return Depends(check)


_connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return _connection_manager


def get_optional_user(request: Request, response: Response, db: Session = Depends(get_db)) -> Optional[models.User]:
    """
    需要知道登入者的 API：與 /auth/session、WebSocket 握手同一個判斷（resolve_login，ADR-0009）。
    access token 過期、refresh token 有效時在這次回應換發 access token，請求照常成功：前端不必讓 token 保持有效，
    401 只代表登入真的失效。沒有登入 cookie 回 None；有登入 cookie 但登入已失效回 401。resolve_login 會查資料庫，同步 def 由 FastAPI 放進 threadpool
    """
    if not has_login_cookies(request.cookies):
        return None
    login = resolve_login(db, request.cookies)
    if login is None:
        # 帶著登入 cookie 但登入已失效：回 401 讓前端照登入失效處理，不悄悄當成匿名（畫面仍顯示登入，結果卻是匿名的）
        raise _not_authenticated()
    if login.renew_access_token:
        set_access_token_cookie(response, login.user.id)
    return login.user


def get_current_user(user: Optional[models.User] = Depends(get_optional_user)) -> models.User:
    """需要登入的 API：判斷同 get_optional_user，未登入或登入已失效回 401（前端當成登入失效處理）。"""
    if user is None:
        raise _not_authenticated()
    return user


def _not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    驗證當前使用者是否為管理員。
    """
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to perform this action")
    return current_user
