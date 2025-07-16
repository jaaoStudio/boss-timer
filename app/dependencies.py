# app/dependencies.py
from fastapi import Depends, WebSocket, status
from fastapi.exceptions import WebSocketException
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional

from app.config import settings
from app.database import models
from app.database.database import get_db
from app.websocket.manager import ConnectionManager


_connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return _connection_manager


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
