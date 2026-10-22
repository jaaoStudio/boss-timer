"""正式機 compose 設定與程式一致（#81）。"""
import os
from pathlib import Path

import yaml

from app.routers import system

ROOT = Path(__file__).resolve().parent.parent
WORKDIR = "/project"   # app/Dockerfile 的 WORKDIR，程式以 COPY . . 放在這裡


def test_maintenance_json_is_mounted_where_the_app_reads_it():
    # 掛到別的路徑時，後台切換維護模式只寫進容器自己的檔案：換 slot 後就不見，blue / green 各自一份
    read_path = f"{WORKDIR}/{Path(os.path.relpath(system.MAINTENANCE_FILE_PATH, ROOT)).as_posix()}"
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    targets = {
        name: [v.split(":")[1] for v in service.get("volumes", []) if "maintenance.json" in v]
        for name, service in compose["services"].items()
        if name.startswith("boss_service_")
    }
    assert targets == {"boss_service_blue": [read_path], "boss_service_green": [read_path]}
