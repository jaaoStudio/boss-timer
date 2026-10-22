"""deploy/：部署時 compose --wait 等新 slot 健康（#52）。"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _seconds(value: str) -> int:
    return int(value.rstrip("s"))


def test_wait_timeout_is_covered_by_start_period():
    # compose 等後端（nginx 的 depends_on）與等 nginx（--wait）各自以 --wait-timeout 計時（Compose 2.35 實測），
    # 所以只要等後端那段全程在 start_period 內：過了 start_period 會改回每 30 秒檢查，稍慢的啟動會多等一輪而逾時
    timeout = int(re.search(r"--wait-timeout (\d+)", (ROOT / "deploy/lib.sh").read_text()).group(1))
    assert timeout == 120
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())
    for slot in ("blue", "green"):
        backend = compose["services"][f"boss_service_{slot}"]["healthcheck"]
        nginx = compose["services"][f"boss_timer_nginx_{slot}"]["healthcheck"]
        assert _seconds(backend["start_period"]) >= timeout, slot
        assert backend["start_interval"] == nginx["start_interval"] == "2s", slot
