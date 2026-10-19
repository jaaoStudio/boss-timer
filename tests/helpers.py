"""測試共用：掛好限流的 FastAPI app 與設定匿名 cookie。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from app.dependencies import limiter, rate_limit_exceeded_handler
from app.utils import anonymous_id


def make_limited_app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    return app


def set_cookies(client: TestClient, anon: str | None = None, signed: bool = True, **extra: str) -> None:
    """清掉 client 的 cookie 後重設。anon 預設以伺服器簽章送出；signed=False 模擬客戶端自己編造的值。"""
    client.cookies.clear()
    if anon:
        client.cookies.set(anonymous_id.COOKIE_NAME, anonymous_id.sign(anon) if signed else anon)
    for name, value in extra.items():
        client.cookies.set(name, value)
