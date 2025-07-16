from fastapi import HTTPException, Request
from jose import JWTError, jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.config import settings

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


async def get_current_user_id(request: Request):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials, token missing or invalid",
    )
    token = request.cookies.get("access_token")

    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user_id
async def get_optional_current_user_id(request: Request) -> Optional[str]:
    try:
     # 直接複用您現有的驗證邏輯
        return await get_current_user_id(request)
    except HTTPException:
        # 如果 get_current_user_id 拋出錯誤 (例如 token 無效或不存在)，
        # 我們捕捉它並回傳 None，代表這是一位匿名使用者。
        return None
