# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Header, Cookie
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import models
from app.database.database import get_db
from app.schemas import auth as auth_schemas
from app.services import auth_service
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google", response_model=auth_schemas.LoginResponse)
async def login_with_google(
        request: auth_schemas.GoogleLoginRequest,
        response: Response,
        db: Session = Depends(get_db)
):
    """
    使用 Google Credential 登入或註冊使用者。
    """
    payload = auth_service.verify_google_token(request.credential)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
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

    # 創建 access token 和 refresh token
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    # 將 refresh token 存儲到資料庫
    auth_service.save_refresh_token(db, user.id, refresh_token)

    # 將 refresh token 設置在 HttpOnly cookie 中
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite='lax',
        secure=settings.env == "production",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60  # 轉換為秒
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite='lax',
        secure=settings.env == "production",
        max_age=settings.access_token_expire_minutes * 60 # 轉換為秒
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": auth_schemas.User.model_validate(user)
    }


@router.post("/refresh", response_model=auth_schemas.TokenResponse)
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

    # 驗證 refresh token
    user_id = auth_service.verify_refresh_token(db, refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # 生成新的 access token
    new_access_token = auth_service.create_access_token(data={"sub": str(user_id)})

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=settings.env == "production",
        samesite="strict",
        max_age=settings.access_token_expire_minutes * 60
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/validate", response_model=auth_schemas.ValidateResponse)
async def validate_token(
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
async def read_users_me(current_user: models.User = Depends(auth_service.get_current_user)):
    """
    獲取當前登入的用戶資訊。
    """
    return current_user


@router.post("/logout")
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

    # 清除 cookie
    response.delete_cookie(key="refresh_token")
    response.delete_cookie(key="access_token")

    return {"message": "Logged out successfully"}


@router.put("/me/preferences", response_model=auth_schemas.User)
async def update_preferences(
        preferences: Dict[str, Any],
        current_user: models.User = Depends(auth_service.get_current_user),
        db: Session = Depends(get_db)
):
    """
    更新當前登入用戶的偏好設定。
    """
    updated_user = auth_service.update_user_preferences(
        db=db, user=current_user, preferences=preferences
    )
    return updated_user