# app/dependencies.py
import ipaddress

from fastapi import Depends, WebSocket, status, HTTPException, Request, Cookie
from fastapi.exceptions import WebSocketException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional, Annotated

from limits import parse_many
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import models
from app.database.database import SessionLocal
from app.websocket.manager import ConnectionManager
from app.services.auth_service import get_current_user # 引入 get_current_user

# IP 天花板 = 個人額度 × 50（假設單一 IP 後最多 50 位真實玩家，見 docs/adr/0007）
IP_CEILING_MULTIPLIER = 50


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
    以單一位址計算的話，每次換位址就是全新的額度。
    """
    ip = get_client_ip(request)
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return f"ip:{ip}"
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
    避免同 IP 有人換 cookie 狂打時連帶擋住登入者（天花板是個人額度的 50 倍，實際上永遠先撞個人額度）。
    """
    return _get_logged_in_user_key(request) or get_ip_rate_limit_key(request)


def get_user_identifier(request: Request) -> str:
    """
    自定義限流識別碼提取函數（個人額度）：
    1. 優先使用登入使用者的 user_id (解析 access_token)
    2. 其次使用訪客的 anonymous_user_id
    3. 最後才退回使用真實 IP
    cookie 可被客戶端任意更換，所以另有 IP 天花板擋繞過，見 rate_limit()。
    """
    user_key = _get_logged_in_user_key(request)
    if user_key:
        return user_key

    anon_id = request.cookies.get("anonymous_user_id")
    if anon_id:
        return f"anon:{anon_id}"

    return get_ip_rate_limit_key(request)

limiter = Limiter(key_func=get_user_identifier, key_style="endpoint")


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
    如果請求既沒有 access_token 也沒有 anonymous_user_id，則會引發 HTTPException。
    這可以防止未經身份驗證的原始請求訪問端點。
    """
    if not access_token and not anonymous_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A session cookie or authentication token is required."
        )
