"""同步的資料庫一律不在 event loop 上執行（ADR-0010，#79）。"""
import asyncio

from fastapi.routing import APIRoute

from app.database.database import get_db
from app.main import app


def _depends_on_db(dependant) -> bool:
    return any(dep.call is get_db or _depends_on_db(dep) for dep in dependant.dependencies)


def test_http_endpoints_using_the_database_are_sync():
    # async def 的端點直接查同步的資料庫會卡住整個 worker 的 event loop（WebSocket 心跳、廣播一起停住）；
    # 宣告成一般的 def，FastAPI 會放到 threadpool 執行。需要廣播時以 anyio.from_thread.run 回到 event loop
    offenders = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute) and _depends_on_db(route.dependant) and asyncio.iscoroutinefunction(route.endpoint)
    ]
    assert offenders == []


def test_broadcast_from_threadpool_runs_on_the_event_loop():
    # def 端點在 threadpool 執行，廣播要回到 event loop 上做：送出佇列是 asyncio.Queue，不是 thread-safe
    import threading

    import anyio

    from app.websocket.manager import ConnectionManager

    manager = ConnectionManager()
    threads = {}

    async def broadcast_to_room(room_id, message):
        threads["broadcast"] = threading.get_ident()

    manager.broadcast_to_room = broadcast_to_room

    async def main():
        threads["loop"] = threading.get_ident()
        await anyio.to_thread.run_sync(manager.broadcast_to_room_from_thread, "ROOMABCDEF", {"type": "x"})

    anyio.run(main)
    assert threads["broadcast"] == threads["loop"]


def test_google_requests_have_timeouts(monkeypatch):
    # 呼叫 Google 沒有逾時的話，Google 卡住時會一直佔著 threadpool 的執行緒（ADR-0010）
    from app.services import auth_service

    seen = {}

    def fake_post(url, data, timeout=None):
        seen["post"] = timeout
        raise RuntimeError("stop")

    def fake_verify(token, request, audience):
        seen["certs"] = request.keywords.get("timeout") if hasattr(request, "keywords") else None
        return {"sub": "g"}

    monkeypatch.setattr(auth_service.python_requests, "post", fake_post)
    monkeypatch.setattr(auth_service.id_token, "verify_oauth2_token", fake_verify)
    auth_service.exchange_google_code("code")
    auth_service.verify_google_token("token")
    assert seen["post"] and seen["certs"]
