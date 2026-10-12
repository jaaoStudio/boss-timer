"""
判斷請求者身分的唯一入口（見 docs/adr/0007）。

限流、verify_user_session、/auth/session（以及之後的 WebSocket）都經這裡，避免各處用不同規則讀同樣的 cookie。
同一個連線只解析一次，結果存在 connection.state；HTTP 與 WebSocket 共同的父類 HTTPConnection 都適用。
"""
from dataclasses import dataclass
from typing import Literal, Optional

from jose import JWTError, jwt
from starlette.requests import HTTPConnection

from app.config import settings
from app.utils import anonymous_id

# user：access token 有效；anon：伺服器簽發的匿名身分；
# legacy：簽章上線前發放、沒有簽章的舊 cookie（過渡期，不可當成已驗證的身分）；none：都沒有
IdentityKind = Literal["user", "anon", "legacy", "none"]


@dataclass(frozen=True)
class Identity:
    kind: IdentityKind
    id: Optional[str] = None


def _decode_user_id(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except (JWTError, ValueError):
        return None
    user_id = payload.get("sub")
    return str(user_id) if user_id else None


def _resolve(cookies: dict[str, str]) -> Identity:
    user_id = _decode_user_id(cookies.get("access_token"))
    if user_id:
        return Identity("user", user_id)
    cookie = cookies.get(anonymous_id.COOKIE_NAME)
    if anon := anonymous_id.verify(cookie):
        return Identity("anon", anon)
    if legacy := anonymous_id.legacy_id(cookie):
        return Identity("legacy", legacy)
    return Identity("none")


def resolve_identity(conn: HTTPConnection) -> Identity:
    cached = getattr(conn.state, "identity", None)
    if cached is None:
        cached = _resolve(conn.cookies)
        conn.state.identity = cached
    return cached
