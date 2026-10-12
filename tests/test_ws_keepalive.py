"""
WebSocket 死連線偵測靠 uvicorn 協定層 ping（#43）。這組設定若在升級時靜靜失效（例如 uvicorn 的
"websockets" 改指向不送 ping 的實作），死連線會一直留在 ConnectionManager、佔用同時連線數上限。
"""
import inspect
import re
from importlib import import_module
from pathlib import Path

from uvicorn.config import WS_PROTOCOLS

DOCKERFILE = Path(__file__).resolve().parent.parent / "app" / "Dockerfile"


def test_dockerfile_pins_websocket_keepalive():
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"UVICORN_WS=websockets\b", content)
    assert re.search(r"UVICORN_WS_PING_INTERVAL=\d+", content)
    assert re.search(r"UVICORN_WS_PING_TIMEOUT=\d+", content)


def test_ping_interval_is_below_cloudflare_idle_limit():
    interval = int(re.search(r"UVICORN_WS_PING_INTERVAL=(\d+)", DOCKERFILE.read_text(encoding="utf-8")).group(1))
    assert 0 < interval < 100   # Cloudflare 的 WebSocket 閒置上限為 100 秒


def test_uvicorn_websockets_impl_sends_keepalive_pings():
    module_path, class_name = WS_PROTOCOLS["websockets"].split(":")
    source = inspect.getsource(getattr(import_module(module_path), class_name))
    assert "ping_interval=self.config.ws_ping_interval" in source
