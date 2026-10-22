"""maintenance.json：正式機兩個 slot 共用主機上同一份（#81）。"""
import json
import os
from pathlib import Path

import yaml

from app.routers import system

ROOT = Path(__file__).resolve().parent.parent


def test_maintenance_file_lives_in_a_mounted_directory():
    # 掛單一檔案的話，主機上以「寫新檔再換上」存檔（編輯器、sed -i、原子寫入）容器看不到；檔案不存在時 Docker 還會建立同名目錄
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    sources = set()
    for name in ("boss_service_blue", "boss_service_green"):
        service = compose["services"][name]
        env = dict(e.split("=", 1) for e in service["environment"])
        mounts = {v.split(":")[1]: v.split(":")[0] for v in service["volumes"]}
        assert os.path.dirname(env["MAINTENANCE_FILE"]) in mounts, name
        sources.add(mounts[os.path.dirname(env["MAINTENANCE_FILE"])])
    assert len(sources) == 1   # 兩個 slot 共用主機上同一個目錄


def test_save_replaces_the_file_atomically(tmp_path, monkeypatch):
    # 兩個 slot 共用同一份：寫到一半被另一個 slot 讀到，會誤判成「沒有維護」並廣播
    path = tmp_path / "maintenance.json"
    path.write_text('{"is_maintenance": false}')
    monkeypatch.setattr(system, "MAINTENANCE_FILE_PATH", str(path))
    seen_while_writing = []
    real_dump = json.dump

    def dump(obj, f, **kwargs):
        seen_while_writing.append(system.read_maintenance_file())
        real_dump(obj, f, **kwargs)

    monkeypatch.setattr(system.json, "dump", dump)
    system.save_maintenance_config({"is_maintenance": True})
    assert seen_while_writing == [{"is_maintenance": False}]
    assert system.read_maintenance_file() == {"is_maintenance": True}
    assert list(tmp_path.iterdir()) == [path]   # 沒留下暫存檔


def test_save_keeps_permissions_and_syncs_before_replacing(tmp_path, monkeypatch):
    # 容器以 root 寫入：不沿用原檔的擁有者與權限，主機上就得 sudo 才改得了。換上前要 fsync，斷電後才不會是空檔
    path = tmp_path / "maintenance.json"
    path.write_text("{}")
    path.chmod(0o664)
    monkeypatch.setattr(system, "MAINTENANCE_FILE_PATH", str(path))
    synced = []
    real_fsync = os.fsync
    monkeypatch.setattr(system.os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd)))
    system.save_maintenance_config({"is_maintenance": True})
    assert path.stat().st_mode & 0o777 == 0o664
    assert synced


def test_admin_toggle_is_broadcast_once(tmp_path, monkeypatch):
    # 端點寫檔後自己廣播、卻沒更新「上次的狀態」時，下一個受保護的請求會再廣播一次同樣的內容（#86）
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    import app.main as main
    from app.dependencies import get_connection_manager, get_current_admin_user

    monkeypatch.setattr(system, "MAINTENANCE_FILE_PATH", str(tmp_path / "maintenance.json"))
    monkeypatch.setattr(system, "last_maintenance_status", dict(system.last_maintenance_status))
    manager = get_connection_manager()
    sent = []

    async def broadcast_to_all(message):
        sent.append(message)

    monkeypatch.setattr(manager, "broadcast_to_all", broadcast_to_all)
    monkeypatch.setitem(main.app.dependency_overrides, get_current_admin_user, lambda: SimpleNamespace(email="admin@example.com"))
    client = TestClient(main.app)
    config = {"is_maintenance": False, "is_ready_for_maintenance": True, "title": "t", "message": "m"}
    assert client.post("/system/maintenance-config", json=config).status_code == 200
    assert client.get("/ws/connections/count").status_code == 200
    assert sent == [{"type": "maintenance_status_update", "data": config}]


def test_failed_broadcast_is_retried(tmp_path, monkeypatch):
    # 廣播前就更新「上次的狀態」的話，廣播失敗後同一個變化永遠不會再廣播
    import asyncio

    monkeypatch.setattr(system, "MAINTENANCE_FILE_PATH", str(tmp_path / "maintenance.json"))
    monkeypatch.setattr(system, "last_maintenance_status", dict(system.last_maintenance_status))
    system.save_maintenance_config({"is_maintenance": True})
    sent = []

    class Manager:
        async def broadcast_to_all(self, message):
            if not sent:
                sent.append(None)
                raise RuntimeError("broadcast failed")
            sent.append(message)

    try:
        asyncio.run(system.refresh_maintenance_status(Manager()))
    except RuntimeError:
        pass
    asyncio.run(system.refresh_maintenance_status(Manager()))
    assert sent[1]["data"]["is_maintenance"] is True


def test_concurrent_refreshes_broadcast_once_even_if_broadcast_yields(tmp_path, monkeypatch):
    # 比較與記下狀態之間若隔著會讓出的 await，同時的兩個請求都會廣播同一個變化
    import asyncio

    monkeypatch.setattr(system, "MAINTENANCE_FILE_PATH", str(tmp_path / "maintenance.json"))
    monkeypatch.setattr(system, "last_maintenance_status", dict(system.last_maintenance_status))
    system.save_maintenance_config({"is_maintenance": True})
    sent = []

    class Manager:
        async def broadcast_to_all(self, message):
            await asyncio.sleep(0)
            sent.append(message)

    async def main():
        await asyncio.gather(*(system.refresh_maintenance_status(Manager()) for _ in range(2)))

    asyncio.run(main())
    assert len(sent) == 1
