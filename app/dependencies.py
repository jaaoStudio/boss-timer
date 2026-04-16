# app/dependencies.py
from fastapi import Depends, WebSocket, status, HTTPException, Request, Cookie
from fastapi.exceptions import WebSocketException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional, Annotated

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import models
from app.database.database import get_db
from app.websocket.manager import ConnectionManager
from app.services.auth_service import get_current_user # 引入 get_current_user
def get_user_identifier(request: Request) -> str:
    """
    自定義限流識別碼提取函數：
    1. 優先使用登入使用者的 user_id (解析 access_token)
    2. 其次使用訪客的 anonymous_user_id
    3. 最後才退回使用真實 IP
    """
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except (JWTError, ValueError):
            pass

    anon_id = request.cookies.get("anonymous_user_id")
    if anon_id:
        return f"anon:{anon_id}"

    return get_remote_address(request)

limiter = Limiter(key_func=get_user_identifier, key_style="endpoint")

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
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    從 WebSocket 連線的 cookie 中解析 JWT，並返回使用者物件。
    如果 token 無效或不存在，則返回 None，代表匿名使用者。
    """
    token = websocket.cookies.get("access_token")
    if not token:
        return None # 匿名使用者

    # Cookie 中的 token 可能包含 "Bearer " 前綴
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None # 無效的 payload

        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        return user # 返回 User 物件或 None

    except (JWTError, ValueError):
        # JWT 錯誤或 user_id 無法轉換為 int
        return None # 無法驗證，視為匿名


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
