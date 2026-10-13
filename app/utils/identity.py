"""
判斷請求者身分（限流 key、匿名身分發放）的唯一入口（見 docs/adr/0007）。

需要完整的 User 物件時改用 auth_service.get_current_user_from_token；兩者都不要自己解析 JWT 或讀 cookie 原值。
"""
from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection
from starlette.websockets import WebSocket

from app.database import models
from app.database.database import SessionLocal
from app.services import auth_service
from app.utils import anonymous_id

# user：access token 有效；anon：伺服器簽發的匿名身分；none：都沒有（含編造的值、過期或類型不符的 token）
IdentityKind = Literal["user", "anon", "none"]


@dataclass(frozen=True)
class Identity:
    kind: IdentityKind
    id: Optional[str] = None


def _resolve(cookies: dict[str, str]) -> Identity:
    if user_id := auth_service.decode_token_user_id(cookies.get("access_token")):
        return Identity("user", user_id)
    return _resolve_anonymous(cookies)


def _resolve_anonymous(cookies: dict[str, str]) -> Identity:
    if anon := anonymous_id.verify(cookies.get(anonymous_id.COOKIE_NAME)):
        return Identity("anon", anon)
    return Identity("none")


def _user_exists(db: Session, user_id: str) -> bool:
    return db.get(models.User, int(user_id)) is not None


def _resolve_websocket(cookies: dict[str, str]) -> Identity:
    access_user = auth_service.decode_token_user_id(cookies.get("access_token"))
    refresh_token = cookies.get("refresh_token")
    if access_user or refresh_token:   # 有登入 cookie 才開 session，匿名握手不碰資料庫
        with SessionLocal() as db:
            if access_user and _user_exists(db, access_user):
                return Identity("user", access_user)
            if refreshed_user := auth_service.verify_refresh_token(db, refresh_token):
                return Identity("user", str(refreshed_user))
    return _resolve_anonymous(cookies)


def resolve_identity(conn: HTTPConnection) -> Identity:
    """
    HTTP 請求：只看 access token 與匿名 cookie，結果存在 request.state，同一個請求的多個限流 key 只解析一次。

    WebSocket 握手：連線會存活很久，背景分頁也會在 access token（30 分鐘，cookie 同時到期）過期後自動重連，
    若只看 access token，登入者重連後會變成匿名、回報沒有記錄者。因此依序：
    1. access token 有效且使用者仍存在 → 登入者
    2. 否則 refresh token 有效（資料庫確認未撤銷；使用者刪除時一併刪除）→ 登入者
    3. 否則伺服器簽發的匿名身分 → 4. 無
    結果存在該連線的 Connection、整條連線固定，這裡不快取。
    ⚠️ WebSocket 有登入 cookie 時會同步查資料庫：async 呼叫端必須以 run_in_threadpool 呼叫，避免卡住 event loop。
    """
    if isinstance(conn, WebSocket):
        return _resolve_websocket(conn.cookies)
    cached = getattr(conn.state, "identity", None)
    if cached is None:
        cached = _resolve(conn.cookies)
        conn.state.identity = cached
    return cached
