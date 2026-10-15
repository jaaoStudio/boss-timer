# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Header, Cookie
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import uuid

from app.database import models
from app.database.database import get_db
from app.dependencies import rate_limit, anonymous_id_mint_allowed, get_current_user
from app.schemas import auth as auth_schemas
from app.services import auth_service
from app.config import settings
from app.utils import anonymous_id
from app.utils.identity import has_login_cookies, resolve_anonymous, resolve_login
from app.utils.login_cookies import cookie_attrs, delete_login_cookies, set_access_token_cookie

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google", response_model=auth_schemas.LoginResponse)
@rate_limit("10/minute")
async def login_with_google(
        request: Request,
        login_data: auth_schemas.GoogleLoginRequest,
        response: Response,
        db: Session = Depends(get_db)
):
    """
    使用 Google Credential 登入或註冊使用者。
    """
    payload = None
    if login_data.code:
        payload = auth_service.exchange_google_code(login_data.code)
    elif login_data.credential:
        payload = auth_service.verify_google_token(login_data.credential)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential or code",
        )

    google_id = payload.get("sub")
    email = payload.get("email")
    display_name = payload.get("name")
    avatar_url = payload.get("picture")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing user info from Google token",
        )

    user = auth_service.get_user_by_google_id(db, google_id=google_id)

    if not user:
        # 創建新使用者
        user_create = auth_schemas.UserCreate(
            google_id=google_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url
        )
        user = auth_service.create_user(db, user_data=user_create)
    else:
        # 更新最後登入時間
        user = auth_service.update_user_last_login(db, user)

    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    # 將 refresh token 存儲到資料庫
    auth_service.save_refresh_token(db, user.id, refresh_token)

    # 將 refresh token 設置在 HttpOnly cookie 中
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,  # 轉換為秒
        **cookie_attrs(),
    )

    access_token = set_access_token_cookie(response, user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": auth_schemas.User.model_validate(user)
    }


@router.post("/refresh", response_model=auth_schemas.TokenResponse)
@rate_limit("30/minute")
async def refresh_token(
        request: Request,
        response: Response,
        db: Session = Depends(get_db)
):
    """
    使用 refresh token 獲取新的 access token。
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    # 驗證 refresh token；無效（過期、被撤銷，例如在其他裝置登入）時一併刪除 cookie：留著沒有用，
    # 之後每次重試都還會拿它來換發
    user_id = auth_service.verify_refresh_token(db, refresh_token)
    if not user_id:
        rejected = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Invalid refresh token"})
        delete_login_cookies(rejected, keys=("refresh_token",))
        return rejected

    new_access_token = set_access_token_cookie(response, user_id)
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/validate", response_model=auth_schemas.ValidateResponse)
@rate_limit("60/minute")
async def validate_token(
        request: Request,
        authorization: str = Header(None),
        access_token: str = Cookie(None),
        db: Session = Depends(get_db)
):
    """
    驗證 access token 的有效性。支援從 Header 或 Cookie 讀取 token。
    """
    try:
        token = None

        # 優先從 Authorization header 讀取
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
        # 如果 header 沒有，則從 cookie 讀取
        elif access_token:
            token = access_token

        if not token:
            raise HTTPException(status_code=401, detail="Missing Token")

        user = auth_service.get_current_user_from_token(token, db)
        return {
            "valid": True,
            "user": auth_schemas.User.model_validate(user)
        }
    except HTTPException:
        return {"valid": False}

@router.get("/me", response_model=auth_schemas.User)
@rate_limit("60/minute")
async def read_users_me(request: Request, current_user: models.User = Depends(get_current_user)):
    """
    獲取當前登入的用戶資訊。
    """
    return current_user


@router.post("/logout")
@rate_limit("10/minute")
async def logout(
        request: Request,
        response: Response,
        db: Session = Depends(get_db)
):
    """
    登出並清除 refresh token。
    """
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # 從資料庫中刪除 refresh token
        auth_service.revoke_refresh_token(db, refresh_token)

    delete_login_cookies(response)

    return {"message": "Logged out successfully"}


@router.put("/me/preferences", response_model=auth_schemas.User)
@rate_limit("30/minute")
async def update_preferences(
        request: Request,
        preferences: Dict[str, Any],
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    更新當前登入用戶的偏好設定。
    """
    updated_user = auth_service.update_user_preferences(
        db=db, user=current_user, preferences=preferences
    )
    return updated_user


@router.post("/session", response_model=auth_schemas.SessionResponse, status_code=status.HTTP_200_OK)
@rate_limit("60/minute")
async def init_session(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
):
    """
    開頁時判斷「你是誰」，登入狀態以這裡的結果為準（ADR-0009）。登入者的判斷與 WebSocket 握手共用 resolve_login：
    - 登入有效 → authenticated（access token 過期、refresh token 有效時順便換發 access token）
    - 有登入 cookie 但登入已失效 → 清掉舊的登入 cookie，改以匿名回應
    - 匿名：簽章正確的匿名 cookie 沿用；沒有、編造或簽章上線前的舊 cookie 發放新身分。舊 cookie 不換發成同一個 UUID：
      匿名 UUID 會廣播給房間所有人，伺服器無法確認送來的人就是本人，換發會讓任何人拿到他人身分的合法簽章
    新發計入每個 IP 的發放上限（ANONYMOUS_ID_MINT_LIMIT），換 cookie 拿新身分因此有上限；撞到上限時回「匿名、暫時沒有身分」，
    以 IP 限流，下次開頁再申請。不回 429：伺服器端的結果相同（拿不到身分），回 429 只會讓前端當成判斷失敗、沿用上次的顯示（#59）。
    匿名身分只回傳 UUID（前端顯示用），cookie 為 httponly。
    """
    cookies = request.cookies
    if has_login_cookies(cookies):
        # resolve_login 會查資料庫（同步）：每次開頁與跨分頁重新判斷都會呼叫，放進 threadpool 免得卡住 WebSocket 等其他工作
        if login := await run_in_threadpool(resolve_login, db, cookies):
            if login.renew_access_token:
                set_access_token_cookie(response, login.user.id)
            return {"status": "authenticated", "user": auth_schemas.User.model_validate(login.user)}
        # 刪掉失效的登入 cookie：refresh cookie 留著的話，WebSocket 握手與之後的請求都還會拿它判斷
        delete_login_cookies(response)

    identity = resolve_anonymous(cookies)
    if identity.kind == "anon":
        return {"status": "anonymous", "anonymous_user_id": identity.id}

    if not anonymous_id_mint_allowed(request):
        return {"status": "anonymous", "anonymous_user_id": None}
    session_id = str(uuid.uuid4())
    response.set_cookie(
        key=anonymous_id.COOKIE_NAME,
        value=anonymous_id.sign(session_id),
        max_age=365 * 24 * 60 * 60,  # 一年
        **cookie_attrs(),
    )
    return {"status": "anonymous", "anonymous_user_id": session_id}
