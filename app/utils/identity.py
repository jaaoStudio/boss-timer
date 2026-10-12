"""
判斷請求者身分（限流 key、匿名身分發放）的唯一入口（見 docs/adr/0007）。

需要完整的 User 物件時改用 auth_service.get_current_user_from_token；兩者都不要自己解析 JWT 或讀 cookie 原值。
"""
from dataclasses import dataclass
from typing import Literal, Optional

from starlette.requests import HTTPConnection, Request

from app.services.auth_service import decode_token_user_id
from app.utils import anonymous_id

# user：access token 有效；anon：伺服器簽發的匿名身分；none：都沒有（含編造的值、過期或類型不符的 token）
IdentityKind = Literal["user", "anon", "none"]


@dataclass(frozen=True)
class Identity:
    kind: IdentityKind
    id: Optional[str] = None


def _resolve(cookies: dict[str, str]) -> Identity:
    if user_id := decode_token_user_id(cookies.get("access_token")):
        return Identity("user", user_id)
    if anon := anonymous_id.verify(cookies.get(anonymous_id.COOKIE_NAME)):
        return Identity("anon", anon)
    return Identity("none")


def resolve_identity(conn: HTTPConnection) -> Identity:
    """
    HTTP 請求的結果存在 request.state，同一個請求的多個限流 key 只解析一次。
    WebSocket 握手不用這個：連線存活很久、access token 會在連線期間過期，改用
    app/routers/websocket.py 的 _resolve_handshake_identity（多了 refresh token 與資料庫確認）。
    """
    if not isinstance(conn, Request):
        return _resolve(conn.cookies)
    cached = getattr(conn.state, "identity", None)
    if cached is None:
        cached = _resolve(conn.cookies)
        conn.state.identity = cached
    return cached
