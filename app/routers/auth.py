# app/routers/auth.py
import anyio
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Header, Cookie
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import uuid

from app.database import models
from app.database.database import SessionLocal, get_db, run_db
from app.dependencies import rate_limit, anonymous_id_mint_allowed, get_current_user
from app.schemas import auth as auth_schemas
from app.services import auth_service
from app.config import settings
from app.utils import anonymous_id
from app.utils.identity import has_login_cookies, resolve_anonymous, resolve_login
from app.utils.login_cookies import cookie_attrs, delete_login_cookies, set_access_token_cookie

router = APIRouter(prefix="/auth", tags=["Authentication"])


# 呼叫 Google 用自己的執行緒上限，不佔預設的 40 條（ADR-0010）：拿著資料庫鎖的請求每一段都要從那 40 條拿一條，
# Google 最多等 20 秒（換 token + 抓憑證），同時登入的人多、Google 又慢時會讓拿著鎖的請求要不到執行緒
GOOGLE_LIMITER = anyio.CapacityLimiter(10)

def _verify_google_payload(login_data: auth_schemas.GoogleLoginRequest) -> Optional[dict]:
    if login_data.code:
        return auth_service.exchange_google_code(login_data.code)
    if login_data.credential:
        return auth_service.verify_google_token(login_data.credential)
    return None


def _login_user(google_id: str, email: str, display_name: Optional[str], avatar_url: Optional[str]) -> tuple[auth_schemas.User, str]:
    """建立或更新使用者並存好 refresh token，回傳 (使用者, refresh token)。拿著資料庫鎖、在 threadpool 執行"""
    with SessionLocal() as db:
        user = auth_service.get_user_by_google_id(db, google_id=google_id)
        if not user:
            user = auth_service.create_user(db, user_data=auth_schemas.UserCreate(
                google_id=google_id, email=email, display_name=display_name, avatar_url=avatar_url,
            ))
        else:
            # 更新最後登入時間，並同步 Google 的名稱與頭像
            user = auth_service.update_user_last_login(db, user, display_name=display_name, avatar_url=avatar_url)
        refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})
        auth_service.save_refresh_token(db, user.id, refresh_token)
        return auth_schemas.User.model_validate(user), refresh_token


@router.post("/google", response_model=auth_schemas.LoginResponse)
@rate_limit("10/minute")
async def login_with_google(
        request: Request,
        login_data: auth_schemas.GoogleLoginRequest,
        response: Response,
):
    """
    使用 Google Credential 登入或註冊使用者。
    呼叫 Google 在資料庫鎖之外（最多等 10 秒，在鎖裡等的話所有人的資料庫工作都要等它），資料庫那段才拿鎖（ADR-0010）。
    兩者都在 threadpool 執行，不在 event loop 上；因此不依賴 get_db（它會讓整個請求拿著鎖）
    """
    payload = await anyio.to_thread.run_sync(_verify_google_payload, login_data, limiter=GOOGLE_LIMITER)

    # 憑證無效回 400 而不是 401：401 在整個後端只代表登入失效，前端遇到 401 會照登入失效處理（ADR-0009）
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google credential or code",
        )

    google_id = payload.get("sub")
    email = payload.get("email")
    # 截斷到欄位長度：超過時建立使用者會丟 DataError、回 500，這個人永遠登入不了（#77）
    # 只有空白的名稱等於沒有名稱，不蓋掉原本的名稱（#77）
    name = (payload.get("name") or "").strip()
    display_name = name[:models.User.display_name.type.length] or None
    avatar_url = payload.get("picture")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing user info from Google token",
        )

    user, refresh_token = await run_db(_login_user, google_id, email, display_name, avatar_url)

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
        "user": user,
    }


@router.post("/refresh", response_model=auth_schemas.TokenResponse)
@rate_limit("30/minute")
def refresh_token(
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
def validate_token(
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
def read_users_me(request: Request, current_user: models.User = Depends(get_current_user)):
    """
    獲取當前登入的用戶資訊。
    """
    return current_user


@router.post("/logout")
@rate_limit("10/minute")
def logout(
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
def update_preferences(
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
def init_session(
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
        if login := resolve_login(db, cookies):
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
