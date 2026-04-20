# app/services/auth_service.py
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from app.database import models, database
from app.schemas import auth as auth_schemas
from app.config import settings

# Google Auth
from google.oauth2 import id_token
from google.auth.transport import requests
import requests as python_requests

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def exchange_google_code(code: str) -> Optional[dict]:
    """
    將 Google Authorization Code 交換為 ID Token，並驗證返回 payload。
    """
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": "postmessage",  # "postmessage" is required for the code flow from frontend
        "grant_type": "authorization_code",
    }
    
    try:
        response = python_requests.post(token_url, data=data)
        response.raise_for_status()
        tokens = response.json()
        id_token_str = tokens.get("id_token")
        
        if not id_token_str:
            return None
            
        return verify_google_token(id_token_str)
    except Exception as e:
        print(f"Failed to exchange code: {e}")
        return None


def verify_google_token(token: str) -> Optional[dict]:
    """
    驗證 Google ID Token 並返回 payload。
    """
    try:
        payload = id_token.verify_oauth2_token(
            token, requests.Request(), settings.google_client_id
        )
        return payload
    except ValueError:
        # Token 無效
        return None


def get_user_by_google_id(db: Session, google_id: str) -> Optional[models.User]:
    """
    通過 Google ID 查找使用者。
    """
    return db.query(models.User).filter(models.User.google_id == google_id).first()


def create_user(db: Session, user_data: auth_schemas.UserCreate) -> models.User:
    """
    創建新使用者。
    """
    db_user = models.User(**user_data.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_last_login(db: Session, user: models.User) -> models.User:
    """
    更新使用者最後登入時間。
    """
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT access token。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT refresh token。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    # 加入隨機 jti (JWT ID) 用於撤銷
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(16)
    })
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def save_refresh_token(db: Session, user_id: int, refresh_token: str):
    """
    將 refresh token 儲存到資料庫。
    """
    # 解析 token 獲取 jti 和過期時間
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        jti = payload.get("jti")
        exp = payload.get("exp")

        # 先刪除該用戶的舊 refresh token
        db.query(models.RefreshToken).filter(
            models.RefreshToken.user_id == user_id
        ).delete()

        # 創建新的 refresh token 記錄
        db_refresh_token = models.RefreshToken(
            user_id=user_id,
            jti=jti,
            token=refresh_token,
            expires_at=datetime.fromtimestamp(exp, timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db.add(db_refresh_token)
        db.commit()

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save refresh token"
        )


def verify_refresh_token(db: Session, refresh_token: str) -> Optional[int]:
    """
    驗證 refresh token 並返回用戶 ID。
    """
    try:
        # 先驗證 JWT 格式和簽名
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])

        # 檢查 token 類型
        if payload.get("type") != "refresh":
            return None

        user_id = int(payload.get("sub"))
        jti = payload.get("jti")

        # 檢查資料庫中是否存在該 refresh token
        db_token = db.query(models.RefreshToken).filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.jti == jti,
            models.RefreshToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if db_token:
            return user_id
        else:
            return None

    except JWTError:
        return None


def revoke_refresh_token(db: Session, refresh_token: str):
    """
    撤銷 refresh token。
    """
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        jti = payload.get("jti")

        db.query(models.RefreshToken).filter(
            models.RefreshToken.jti == jti
        ).delete()
        db.commit()

    except JWTError:
        pass  # 忽略無效的 token


def get_current_user_from_token(token: str, db: Session) -> models.User:
    """
    從 token 字符串解析並獲取當前使用者。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        # 檢查 token 類型
        if payload.get("type") != "access":
            raise credentials_exception

        user_id: int = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_user(access_token: str | None = Cookie(None), db: Session = Depends(database.get_db)) -> models.User:
    """
    從 access_token cookie 中解析 JWT 並獲取當前使用者。
    """
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user_from_token(access_token, db)


def update_user_preferences(db: Session, user: models.User, preferences: dict) -> models.User:
    """
    更新使用者偏好設定。
    只允許已知的偏好鍵，防止任意 JSON 注入。
    """
    ALLOWED_PREFERENCE_KEYS = {"showRecordHistory", "channelViewMode", "favoriteBossIds", "bossTrackerLayout"}

    # 只保留允許的 key
    filtered_preferences = {k: v for k, v in preferences.items() if k in ALLOWED_PREFERENCE_KEYS}

    if not filtered_preferences:
        return user  # 沒有有效的偏好設定要更新

    # 如果 user.preferences 是 None，初始化為一個空字典
    if user.preferences is None:
        user.preferences = {}

    # 確保我們是在一個字典上操作，以防 user.preferences 不是字典
    current_preferences = user.preferences.copy() if isinstance(user.preferences, dict) else {}

    # 合併新的偏好設定
    current_preferences.update(filtered_preferences)
    user.preferences = current_preferences

    db.commit()
    db.refresh(user)
    return user

