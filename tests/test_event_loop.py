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

    def enqueue_all(websockets, message):
        threads["broadcast"] = threading.get_ident()

    manager._enqueue_all = enqueue_all

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


def test_async_functions_do_not_open_database_sessions():
    # Depends(get_db) 以外的寫法：在 async 函式裡直接開 SessionLocal() 一樣會在 event loop 上查資料庫
    # （WebSocket handler、背景工作）。查資料庫的部分要寫成同步函式、放進 threadpool
    import ast
    import pathlib

    offenders = []
    for path in pathlib.Path("app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.AsyncFunctionDef):
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "SessionLocal":
                        offenders.append(f"{path}:{node.name}")
    assert offenders == []


def test_boss_update_is_broadcast_before_discord_is_scheduled(monkeypatch):
    # Discord 通知要寫 Redis：Redis 慢的時候，房間不該等它才看到回報
    from types import SimpleNamespace

    from app.services import boss_service
    from app.services.boss_service import BossService

    order = []
    record = SimpleNamespace(id=1)
    monkeypatch.setattr(BossService, "_validate_room_exists", staticmethod(lambda db, room_id: SimpleNamespace(last_active=None)))
    monkeypatch.setattr(BossService, "_get_boss_type_by_id", staticmethod(lambda db, boss_type_id: None))
    monkeypatch.setattr(BossService, "_calculate_respawn_times", staticmethod(lambda db, rec, boss_type: {}))
    monkeypatch.setattr(BossService, "_create_boss_record", staticmethod(lambda db, rec, times, identity: record))
    monkeypatch.setattr(boss_service, "BossRecordResponse", SimpleNamespace(
        model_validate=lambda obj: SimpleNamespace(model_dump=lambda mode: {})))
    monkeypatch.setattr(boss_service.NotificationPolicy, "notify", staticmethod(lambda rec, room, db: order.append("notify")))

    class FakeQuery:
        def options(self, *a): return self
        def filter(self, *a): return self
        def first(self): return record

    db = SimpleNamespace(query=lambda model: FakeQuery())
    payload = SimpleNamespace(room_id="ROOMABCDEF", boss_type_id=1)
    BossService.record_boss(db, payload, None, broadcast=lambda message: order.append("broadcast"))
    assert order == ["broadcast", "notify"]


def test_database_lane_runs_one_at_a_time():
    # 程式隱含依賴「資料庫操作依序執行」（以前卡住 event loop 等於自動排隊）：通道一次只跑一個，但不在 event loop 上
    import anyio

    from app.dependencies import configure_database_lane

    async def main():
        configure_database_lane()
        return anyio.to_thread.current_default_thread_limiter().total_tokens

    assert anyio.run(main) == 1


def test_google_calls_do_not_take_the_database_lane(monkeypatch):
    # 呼叫 Google 最多等 10 秒：佔住一次一個的資料庫通道的話，所有人的資料庫操作都要等它
    import anyio

    from app.routers import auth

    used = []
    real_run_sync = anyio.to_thread.run_sync

    async def spy(fn, *args, limiter=None, **kwargs):
        used.append((getattr(fn, "__name__", ""), limiter))
        return await real_run_sync(fn, *args, limiter=limiter, **kwargs)

    monkeypatch.setattr(auth.anyio.to_thread, "run_sync", spy)
    monkeypatch.setattr(auth.auth_service, "verify_google_token", lambda credential: None)
    from fastapi.testclient import TestClient
    from tests.helpers import make_limited_app

    app = make_limited_app()
    app.include_router(auth.router)
    with TestClient(app) as client:
        client.post("/auth/google", json={"credential": "bad"}, headers={"CF-Connecting-IP": "203.0.113.7"})
    google = [limiter for name, limiter in used if name == "_verify_google_payload"]
    assert google and google[0] is auth.GOOGLE_LIMITER


def test_maintenance_file_is_read_in_the_database_lane(monkeypatch):
    # 維護設定檔的讀寫都走同一條通道：管理員寫到一半時不會被讀到（誤判成「沒有維護」並廣播）
    import threading

    import anyio

    from app import main

    threads = {}
    monkeypatch.setattr(main, "read_maintenance_file", lambda: threads.setdefault("read", threading.get_ident()) and {})

    class Manager:
        async def broadcast_to_all(self, message):
            pass

    async def run():
        threads["loop"] = threading.get_ident()
        await main.check_maintenance_mode(Manager())

    anyio.run(run)
    assert threads["read"] != threads["loop"]
