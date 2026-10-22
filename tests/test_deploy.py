"""deploy/：部署時 compose --wait 等新 slot 健康（#52）。"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _seconds(value: str) -> int:
    return int(value.rstrip("s"))


def test_wait_timeout_is_covered_by_start_period():
    # 過了 start_period 會改回每 30 秒檢查。後端在自己的 start_period 內健康就要算成功：
    # nginx 等後端健康才啟動，期限還要留下 nginx 的 start_period
    timeout = int(re.search(r"--wait-timeout (\d+)", (ROOT / "deploy/lib.sh").read_text()).group(1))
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    for slot in ("blue", "green"):
        backend = compose["services"][f"boss_service_{slot}"]["healthcheck"]
        nginx = compose["services"][f"boss_timer_nginx_{slot}"]["healthcheck"]
        assert _seconds(backend["start_period"]) + _seconds(nginx["start_period"]) <= timeout, slot
        assert backend["start_interval"] == nginx["start_interval"] == "2s", slot
