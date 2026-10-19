from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Literal, Optional, Dict, Any
from datetime import datetime


class GoogleLoginRequest(BaseModel):
    credential: Optional[str] = None
    code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: "User"


class ValidateRequest(BaseModel):
    token: str


class ValidateResponse(BaseModel):
    valid: bool
    user: Optional["User"] = None


class User(BaseModel):
    id: int
    google_id: str
    email: str
    display_name: Optional[str] = None   # Google 沒有回傳名稱時是 NULL（#65）
    avatar_url: Optional[str] = None
    preferences: dict = {}
    created_at: datetime
    last_login_at: Optional[datetime] = None
    is_admin: Optional[bool]

    model_config = ConfigDict(from_attributes=True)


class PublicUser(BaseModel):
    """Public-facing user info — hides google_id, email, is_admin."""
    id: int
    display_name: Optional[str] = None   # Google 沒有回傳名稱時是 NULL（#65）
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RecorderInfo(BaseModel):
    """Structured anonymous recorder info — prevents arbitrary JSON injection."""
    anonymous_id: Optional[str] = Field(None, max_length=100)
    anonymous_name: Optional[str] = Field(None, max_length=20)



class UserCreate(BaseModel):
    google_id: str
    email: str
    display_name: Optional[str] = None   # Google 沒有回傳名稱時是 NULL（#65）
    avatar_url: Optional[str] = None


class TokenData(BaseModel):
    user_id: int


class SessionResponse(BaseModel):
    """/auth/session：登入者帶 user，匿名者帶 anonymous_user_id（暫時沒有身分時為 None），見 ADR-0009。"""
    status: Literal["authenticated", "anonymous"]
    user: Optional[User] = None
    anonymous_user_id: Optional[str] = None
