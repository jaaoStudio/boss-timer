"""同步的資料庫一律不在 event loop 上執行（ADR-0010，#79）。"""
import ast
import asyncio
import pathlib
import threading
import time
from types import SimpleNamespace

import anyio
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.database.database import db_lock, get_db, run_db
from app.main import app
from app.routers import auth
from app.services import auth_service, boss_service
from app.services.boss_service import BossService
from app.websocket.manager import ConnectionManager


def _depends_on_db(dependant) -> bool:
    return any(dep.call is get_db or _depends_on_db(dep) for dep in dependant.dependencies)


def test_http_endpoints_using_the_database_are_sync():
    # async def 的端點直接查同步的資料庫會卡住整個 worker 的 event loop（WebSocket 心跳、廣播一起停住）；
    # 宣告成一般的 def，FastAPI 會放到 threadpool 執行。需要廣播時以 manager.*_from_thread 回到 event loop
    offenders = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute) and _depends_on_db(route.dependant) and asyncio.iscoroutinefunction(route.endpoint)
    ]
    assert offenders == []


def test_broadcast_from_threadpool_runs_on_the_event_loop():
    # def 端點在 threadpool 執行，廣播要回到 event loop 上做：送出佇列是 asyncio.Queue，不是 thread-safe
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


def test_database_lock_is_strictly_exclusive():
    # 資料庫工作依序執行（ADR-0010）：anyio 的 CapacityLimiter 交接名額時，醒來前會被別人搶先，兩件事同時跑；
    # 這把鎖不可以
    running, overlaps = [0], []
    guard = threading.Lock()

    def work():
        with guard:
            running[0] += 1
            overlaps.append(running[0])
        time.sleep(0.001)
        with guard:
            running[0] -= 1

    async def job():
        async with db_lock():
            await anyio.to_thread.run_sync(work)

    async def main():
        async with anyio.create_task_group() as tg:
            for _ in range(200):
                tg.start_soon(job)

    anyio.run(main)
    assert max(overlaps) == 1


def test_database_lock_covers_the_whole_request():
    # FastAPI 把一個請求拆成好幾段丟進 threadpool（dependency、端點本體、收尾）。以前「一次一個」的單位是一段，
    # 兩個請求的段會交錯；依序執行的單位要是整個請求
    events = []
    guard = threading.Lock()
    app = FastAPI()

    def first_step(db=Depends(get_db)):
        with guard:
            events.append("start")
        time.sleep(0.02)
        return db

    @app.get("/work")
    def work(db=Depends(first_step)):
        time.sleep(0.02)
        with guard:
            events.append("end")
        return {}

    async def main():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with anyio.create_task_group() as tg:
                for _ in range(5):
                    tg.start_soon(client.get, "/work")

    anyio.run(main)
    assert events == ["start", "end"] * 5, events


def test_google_is_called_outside_the_database_lock(monkeypatch):
    # 呼叫 Google 最多等 10 秒：在鎖裡等的話，所有人的資料庫工作都要等它
    held = []

    def verify(credential):
        held.append(anyio.from_thread.run_sync(lambda: db_lock().locked()))
        return None

    monkeypatch.setattr(auth.auth_service, "verify_google_token", verify)
    app = FastAPI()
    app.include_router(auth.router)
    with TestClient(app) as client:
        client.post("/auth/google", json={"credential": "bad"}, headers={"CF-Connecting-IP": "203.0.113.7"})
    assert held == [False]


def test_run_db_gives_up_waiting_for_the_lock_after_the_timeout():
    async def main():
        held = anyio.Event()

        async def hold():
            async with db_lock():
                held.set()
                await anyio.sleep(1)

        async with anyio.create_task_group() as tg:
            tg.start_soon(hold)
            await held.wait()
            with pytest.raises(TimeoutError):
                await run_db(lambda: None, lock_timeout=0.05)
            tg.cancel_scope.cancel()
        assert await run_db(lambda x: x + 1, 1) == 2   # 放開後照常執行、回傳結果

    anyio.run(main)


def test_google_calls_do_not_take_the_default_threads(monkeypatch):
    # 拿著資料庫鎖的請求每一段都要從預設的 40 條執行緒拿一條。Google 最多等 20 秒（換 token + 抓憑證）：
    # 40 個人同時登入、Google 又慢時，拿著鎖的請求要不到執行緒，所有資料庫工作一起停住
    borrowed = []

    def verify(credential):
        borrowed.append(anyio.from_thread.run_sync(lambda: anyio.to_thread.current_default_thread_limiter().borrowed_tokens))
        return None

    monkeypatch.setattr(auth.auth_service, "verify_google_token", verify)
    app = FastAPI()
    app.include_router(auth.router)
    with TestClient(app) as client:
        client.post("/auth/google", json={"credential": "bad"}, headers={"CF-Connecting-IP": "203.0.113.8"})
    assert borrowed == [0]


def test_session_is_closed_even_when_the_request_is_cancelled(monkeypatch):
    # 請求被取消（伺服器關閉、middleware 取消）時，收尾也要把連線還回連線池：
    # 被取消的 scope 裡一 await 就會再被取消，close 沒保護的話不會執行
    from app.database import database

    closed = []
    monkeypatch.setattr(database, "SessionLocal", lambda: SimpleNamespace(close=lambda: closed.append(True)))

    async def main():
        with anyio.CancelScope() as scope:
            requests = get_db()
            await requests.__anext__()
            scope.cancel()
            await requests.aclose()

    anyio.run(main)
    assert closed == [True]


def test_handshake_lock_timeout_is_shorter_than_the_frontend_gives_up():
    # 握手等鎖要比前端放棄握手（CONNECT_TIMEOUT_MS）短，否則被放棄的握手仍在排隊、佇列越來越長；
    # 也不能太短：部署後幾百個分頁同時重連時，加入房間要排一陣子（PR #80 第 5 輪）
    import re

    from app.routers import websocket

    source = pathlib.Path("frontend/src/stores/websocketStore.ts").read_text(encoding="utf-8")
    frontend_seconds = int(re.search(r"CONNECT_TIMEOUT_MS = (\d+)", source).group(1)) / 1000
    assert 10 <= websocket.HANDSHAKE_LOCK_TIMEOUT_SECONDS < frontend_seconds


def test_google_timeout_is_a_failed_login_not_a_server_error(monkeypatch, caplog):
    # Google 逾時丟 TransportError：照憑證無效處理（回 400、前端顯示登入失敗），不是 500 跳錯誤頁
    from google.auth.exceptions import TransportError

    def slow(*args, **kwargs):
        raise TransportError("read timed out")

    monkeypatch.setattr(auth_service.id_token, "verify_oauth2_token", slow)
    assert auth_service.verify_google_token("credential") is None
    # 和憑證無效分得出來：Google 故障時 log 看得到
    assert [r.levelname for r in caplog.records if "Google" in r.getMessage()] == ["WARNING"]
