"""
匿名身分 cookie 的簽章與驗證（見 docs/adr/0007）。

cookie 值為「UUID.簽章」，簽章以伺服器密鑰對 UUID 做 HMAC-SHA256。客戶端編造的值算不出正確簽章，
不會被當成匿名身分；要拿到新身分只能經 /auth/session 申請，由伺服器限制發放速度。
"""
import base64
import hashlib
import hmac
import re
from typing import Optional

from app.config import settings

COOKIE_NAME = "anonymous_user_id"
_UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_SIGNATURE = re.compile(r"[A-Za-z0-9_-]{43}")   # base64url(SHA-256) 去掉 padding


def _signature(anonymous_id: str) -> str:
    digest = hmac.new(
        settings.secret_key.encode(),
        f"{COOKIE_NAME}:{anonymous_id}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def sign(anonymous_id: str) -> str:
    """產生 cookie 值。"""
    return f"{anonymous_id}.{_signature(anonymous_id)}"


def verify(cookie_value: Optional[str]) -> Optional[str]:
    """簽章正確時回傳匿名 UUID，否則回傳 None。"""
    anonymous_id, _, signature = (cookie_value or "").rpartition(".")
    # 先確認格式：compare_digest 遇到非 ASCII 字串會拋 TypeError，客戶端送來的 cookie 不可直接比對
    if not _UUID4.fullmatch(anonymous_id) or not _SIGNATURE.fullmatch(signature):
        return None
    if not hmac.compare_digest(signature, _signature(anonymous_id)):
        return None
    return anonymous_id
