"""
登入相關 cookie 的設定與刪除，/auth 路由與需要登入的 API 依賴（換發 access token）共用。
"""
from fastapi import Response

from app.config import settings
from app.services import auth_service


def cookie_attrs() -> dict:
    # 所有 cookie 設定與刪除共用的屬性：刪除時屬性要與設定時相同才刪得掉
    return {"httponly": True, "secure": settings.env == "production", "samesite": "lax"}


def set_access_token_cookie(response: Response, user_id: int) -> str:
    access_token = auth_service.create_access_token(data={"sub": str(user_id)})
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **cookie_attrs(),
    )
    return access_token


def delete_login_cookies(response: Response, keys: tuple[str, ...] = ("access_token", "refresh_token")) -> None:
    for key in keys:
        response.delete_cookie(key=key, **cookie_attrs())
