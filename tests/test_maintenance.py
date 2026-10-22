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
    for name in ("boss_service_blue", "boss_service_green"):
        service = compose["services"][name]
        env = dict(e.split("=", 1) for e in service["environment"])
        targets = [v.split(":")[1] for v in service["volumes"]]
        assert os.path.dirname(env["MAINTENANCE_FILE"]) in targets, name


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
