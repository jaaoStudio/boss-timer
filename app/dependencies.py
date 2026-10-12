# app/dependencies.py
import ipaddress

from fastapi import Depends, WebSocket, status, HTTPException, Request, Cookie
from fastapi.exceptions import WebSocketException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional, Annotated

from limits import parse, parse_many
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import models
from app.database.database import SessionLocal
from app.websocket.manager import ConnectionManager
from app.services.auth_service import get_current_user # 引入 get_current_user
from app.utils import anonymous_id

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


def _get_logged_in_user_key(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except (JWTError, ValueError):
        return None
    user_id = payload.get("sub")
    return f"user:{user_id}" if user_id else None


def get_ip_ceiling_key(request: Request) -> str:
    """
    IP 天花板的 key。登入者無法更換身分，不需要天花板擋繞過，改用自己的 user key，
    避免同 IP 有人換 cookie 狂打時連帶擋住登入者（天花板遠大於個人額度，實際上永遠先撞個人額度）。
    """
    return _get_logged_in_user_key(request) or get_ip_rate_limit_key(request)


def get_user_identifier(request: Request) -> str:
    """
    自定義限流識別碼提取函數（個人額度）：
    1. 優先使用登入使用者的 user_id (解析 access_token)
    2. 其次使用訪客的匿名身分（cookie 簽章正確才算；編造或舊版無簽章的值退回 IP）
    3. 最後才退回使用真實 IP
    """
    user_key = _get_logged_in_user_key(request)
    if user_key:
        return user_key

    anon_id = anonymous_id.verify(request.cookies.get(anonymous_id.COOKIE_NAME))
    if anon_id:
        return f"anon:{anon_id}"

    return get_ip_rate_limit_key(request)

limiter = Limiter(key_func=get_user_identifier, key_style="endpoint")


def allow_anonymous_id_mint(request: Request) -> bool:
    """發放新匿名身分前呼叫：以真實 IP 計數，超過 ANONYMOUS_ID_MINT_LIMIT 回傳 False。"""
    return limiter.limiter.hit(parse(ANONYMOUS_ID_MINT_LIMIT), "anonymous_id_mint", get_ip_rate_limit_key(request))


def scale_limit(limit_value: str, factor: int) -> str:
    """把 "15/minute;50/day" 的每條上限乘上 factor。"""
    return ";".join(
        f"{item.amount * factor} per {item.multiples} {item.GRANULARITY.name}"
        for item in parse_many(limit_value)
    )


def rate_limit(limit_value: str):
    """
    雙層限流（見 docs/adr/0007）：
    - 個人額度：limit_value，以登入身分 / anonymous_user_id cookie 計算，維持公平
    - IP 天花板：limit_value × IP_CEILING_MULTIPLIER，以真實 IP（IPv6 以 /64）計算，擋換 cookie 繞過與灌爆；
      登入者改以自己的身分計算，不受同 IP 其他人影響
    學校等共用 IP 的玩家各用各的個人額度，只有換 cookie 狂打才會撞到天花板。
    """
    personal = limiter.limit(limit_value)
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
    從 WebSocket 連線的 cookie 中解析 JWT，並返回使用者物件。
    如果 token 無效或不存在，則返回 None，代表匿名使用者。
    使用短暫的 DB session，不長持連線。
    """
    token = websocket.cookies.get("access_token")
    if not token:
        return None

    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        with SessionLocal() as db:
            user = db.query(models.User).filter(models.User.id == int(user_id)).first()
            return user

    except (JWTError, ValueError):
        return None


async def verify_user_session(
    access_token: Annotated[str | None, Cookie()] = None,
    anonymous_user_id: Annotated[str | None, Cookie()] = None,
):
    """
    一個依賴項，用於驗證請求是否具有有效的用戶會話（已登錄或匿名）。
    沒有 access_token、匿名 cookie 也不是伺服器發的，就引發 HTTPException。
    過渡期也接受簽章上線前的舊 UUID cookie：部署前就開著的分頁在重新整理（經 /auth/session 換發）前
    仍拿著舊 cookie，若直接拒絕，前端的 401 處理會把匿名使用者踢出房間。限流仍只認有簽章的身分。
    """
    has_anonymous_session = bool(
        anonymous_id.verify(anonymous_user_id) or anonymous_id.legacy_id(anonymous_user_id)
    )
    if not access_token and not has_anonymous_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A session cookie or authentication token is required."
        )
