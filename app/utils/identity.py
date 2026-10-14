"""
判斷請求者身分（登入者、限流 key、匿名身分發放）的唯一入口（見 docs/adr/0007、0009）。

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

# user：access token 有效（WebSocket 另外接受有效的 refresh token）；anon：伺服器簽發的匿名身分；none：都沒有（含編造的值、過期或類型不符的 token）
IdentityKind = Literal["user", "anon", "none"]


@dataclass(frozen=True)
class Identity:
    kind: IdentityKind
    id: Optional[str] = None


def _resolve(cookies: dict[str, str]) -> Identity:
    if user_id := auth_service.decode_token_user_id(cookies.get("access_token")):
        return Identity("user", user_id)
    return resolve_anonymous(cookies)


def resolve_anonymous(cookies: dict[str, str]) -> Identity:
    """只看伺服器簽發的匿名 cookie：anon 或 none。"""
    if anon := anonymous_id.verify(cookies.get(anonymous_id.COOKIE_NAME)):
        return Identity("anon", anon)
    return Identity("none")


@dataclass(frozen=True)
class Login:
    user: models.User
    # access token 無效、以 refresh token 認出：/auth/session 要換發 access token
    from_refresh_token: bool


def has_login_cookies(cookies: dict[str, str]) -> bool:
    """有能解開的 access / refresh token（不查資料庫）。空值或編造的 cookie 不算，不會被當成失效的登入。"""
    return bool(auth_service.decode_token_user_id(cookies.get("access_token"))
                or auth_service.decode_token_user_id(cookies.get("refresh_token"), token_type="refresh"))


def _get_user(db: Session, user_id: str | int) -> Optional[models.User]:
    return db.get(models.User, int(user_id))


def resolve_login(db: Session, cookies: dict[str, str]) -> Optional[Login]:
    """
    登入者的判斷，/auth/session 與 WebSocket 握手共用，兩邊不會判斷出不同結果（ADR-0009）：
    1. access token 有效且使用者仍存在 → 登入者
    2. 否則 refresh token 有效（資料庫確認未撤銷；使用者刪除時一併刪除）→ 登入者，access token 需要換發
    3. 否則 None：登入已失效或從未登入
    """
    access_user = auth_service.decode_token_user_id(cookies.get("access_token"))
    if access_user and (user := _get_user(db, access_user)):
        return Login(user, from_refresh_token=False)
    refreshed_user = auth_service.verify_refresh_token(db, cookies.get("refresh_token"))
    if refreshed_user and (user := _get_user(db, refreshed_user)):
        return Login(user, from_refresh_token=True)
    return None


def _resolve_websocket(cookies: dict[str, str]) -> Identity:
    if has_login_cookies(cookies):   # 有登入 cookie 才開 session，匿名握手不碰資料庫
        with SessionLocal() as db:
            if login := resolve_login(db, cookies):
                return Identity("user", str(login.user.id))
    return resolve_anonymous(cookies)


def resolve_identity(conn: HTTPConnection) -> Identity:
    """
    HTTP 請求：只看 access token 與匿名 cookie，結果存在 request.state，同一個請求的多個限流 key 只解析一次。

    WebSocket 握手：連線會存活很久，背景分頁也會在 access token（30 分鐘，cookie 同時到期）過期後自動重連，
    若只看 access token，登入者重連後會變成匿名、回報沒有記錄者。因此先以 resolve_login 判斷登入者
    （與 /auth/session 相同），否則伺服器簽發的匿名身分，否則無。
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
