"""測試共用：測試用的 FastAPI app 與設定匿名 cookie。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.utils import anonymous_id


def make_limited_app() -> FastAPI:
    # 限流是路由層級的 dependency（rate_limit()），不需要另外掛 middleware 或例外處理
    return FastAPI()


def set_cookies(client: TestClient, anon: str | None = None, signed: bool = True, **extra: str) -> None:
    """清掉 client 的 cookie 後重設。anon 預設以伺服器簽章送出；signed=False 模擬客戶端自己編造的值。"""
    client.cookies.clear()
    if anon:
        client.cookies.set(anonymous_id.COOKIE_NAME, anonymous_id.sign(anon) if signed else anon)
    for name, value in extra.items():
        client.cookies.set(name, value)
