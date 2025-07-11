# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import models
from app.database.database import get_db
from app.schemas import auth as auth_schemas
from app.services import auth_service
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google", response_model=auth_schemas.Token)
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

    # 創建 access token
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})

    # 將 token 設置在 cookie 中
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite='lax',
        secure=True, # 在生產環境中應為 True
        max_age=settings.access_token_expire_minutes * 60
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": auth_schemas.User.from_orm(user)
    }


@router.get("/me", response_model=auth_schemas.User)
async def read_users_me(current_user: models.User = Depends(auth_service.get_current_user)):
    """
    獲取當前登入的用戶資訊。
    """
    return current_user


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
