"""deploy/：部署時 compose --wait 等新 slot 健康（#52）。"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _seconds(value: str) -> int:
    return int(value.rstrip("s"))


def test_wait_timeout_is_covered_by_start_period():
    # 過了 start_period 會改回每 30 秒檢查：稍慢的啟動要多等一輪，可能超過 --wait-timeout 而被判定部署失敗
    timeout = int(re.search(r"--wait-timeout (\d+)", (ROOT / "deploy/lib.sh").read_text()).group(1))
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    for slot in ("blue", "green"):
        check = compose["services"][f"boss_service_{slot}"]["healthcheck"]
        assert _seconds(check["start_period"]) >= timeout, slot
        assert check["start_interval"] == "2s", slot
