from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

# 用於接收前端傳來的 Google credential
class GoogleLoginRequest(BaseModel):
    credential: str

# 用於在服務層內部創建使用者
class UserCreate(BaseModel):
    google_id: str
    email: EmailStr
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

# 用於 API 回應的使用者基本資訊
class User(BaseModel):
    id: int
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = {}

    class Config:
        from_attributes = True

# 用於回傳 JWT token
class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

# 用於解析 JWT token 後的資料
class TokenData(BaseModel):
    user_id: Optional[int] = None
