"""
匿名身分 cookie 的簽章與驗證（見 docs/adr/0007）。

cookie 值為「UUID.簽章」，簽章以伺服器密鑰對 UUID 做 HMAC-SHA256。客戶端編造的值算不出正確簽章，
不會被當成匿名身分；要拿到新身分只能經 /auth/session 申請，由伺服器限制發放速度。
"""
import base64
import hashlib
import hmac
import uuid
from typing import Optional

from app.config import settings

COOKIE_NAME = "anonymous_user_id"


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
    anonymous_id, separator, signature = (cookie_value or "").rpartition(".")
    if not separator or not hmac.compare_digest(signature, _signature(anonymous_id)):
        return None
    return anonymous_id


def legacy_id(cookie_value: Optional[str]) -> Optional[str]:
    """
    簽章上線前發放、沒有簽章的舊 cookie（標準格式的 UUIDv4）。
    只用於換發成同一個 UUID 的簽章版本，讓舊紀錄的記錄者仍對得上；不可當成已驗證的身分。
    """
    if not cookie_value:
        return None
    try:
        parsed = uuid.UUID(cookie_value)
    except ValueError:
        return None
    return cookie_value if parsed.version == 4 and str(parsed) == cookie_value else None
