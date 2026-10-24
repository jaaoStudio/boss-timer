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


# ── 每個 slot 一個專用網路，nginx 照映像內建的設定轉給 boss_service（#50）──
SLOTS = ("blue", "green")


def _services():
    return yaml.safe_load((ROOT / "deploy/docker-compose.yaml").read_text())["services"]


def _networks(service):
    nets = service["networks"]
    return nets if isinstance(nets, dict) else {n: None for n in nets}


def test_nginx_reaches_only_its_own_slot_backend():
    # 兩個後端都在 boss_network，不能在那裡加同名別名：nginx 會隨機轉給兩邊、同一房間拆成兩群
    services = _services()
    for slot in SLOTS:
        assert set(_networks(services[f"boss_timer_nginx_{slot}"])) == {f"boss_{slot}", "traefik-net"}, slot
        backend = _networks(services[f"boss_service_{slot}"])
        assert set(backend) == {"boss_network", f"boss_{slot}"}, slot   # boss_network 接 db / redis
        assert backend[f"boss_{slot}"]["aliases"] == ["boss_service"], slot


def test_nginx_uses_the_config_built_into_the_image():
    # 只留 frontend/nginx/nginx.conf 一份：正式機不再掛各 slot 的設定檔，回滾到舊映像也是同一份設定
    conf = (ROOT / "frontend/nginx/nginx.conf").read_text()
    assert "server boss_service:1254 resolve;" in conf   # 後端重啟換了 IP 時跟著更新，否則一直回 502
    assert "resolver 127.0.0.11" in conf
    assert not (ROOT / "deploy/frontend").exists()
    for slot in SLOTS:
        assert "volumes" not in _services()[f"boss_timer_nginx_{slot}"], slot


def test_slots_differ_only_by_name():
    # 兩個 slot 以 YAML anchor 共用設定，展開後只差 slot 名稱（tag、container_name、depends_on、網路）
    services = _services()
    for kind in ("boss_service", "boss_timer_nginx"):
        blue = yaml.safe_dump(services[f"{kind}_blue"])
        green = yaml.safe_dump(services[f"{kind}_green"])
        assert blue.replace("blue", "green").replace("BLUE", "GREEN") == green, kind
