# app/services/auth_service.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import models, database
from app.schemas import auth as auth_schemas
from app.config import settings

# Google Auth
from google.oauth2 import id_token
from google.auth.transport import requests

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


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
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)) -> models.User:
    """
    解析 JWT 並獲取當前使用者。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = auth_schemas.TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user


def update_user_preferences(db: Session, user: models.User, preferences: dict) -> models.User:
    """
    更新使用者偏好設定。
    """
    user.preferences = preferences
    db.commit()
    db.refresh(user)
    return user
