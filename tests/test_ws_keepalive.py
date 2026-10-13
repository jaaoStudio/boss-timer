"""
WebSocket 死連線偵測靠 uvicorn 協定層 ping（#43、ADR-0008）。這組設定若在升級時靜靜失效（例如 uvicorn 的
"websockets" 改指向不送 ping 的實作），死連線會一直留在 ConnectionManager、佔用同時連線數上限。
"""
import asyncio
import re
from pathlib import Path

from uvicorn.config import Config
from uvicorn.server import ServerState

from app.websocket.manager import HEARTBEAT_INTERVAL_SECONDS

DOCKERFILE = Path(__file__).resolve().parent.parent / "app" / "Dockerfile"


def dockerfile_env() -> dict[str, str]:
    content = DOCKERFILE.read_text(encoding="utf-8")
    return dict(re.findall(r"\b(UVICORN_WS\w*)=(\S+)", content))


CLOUDFLARE_IDLE_LIMIT_SECONDS = 100   # Cloudflare 的 WebSocket 閒置上限


def test_heartbeat_and_ping_are_below_cloudflare_idle_limit():
    assert 0 < HEARTBEAT_INTERVAL_SECONDS < CLOUDFLARE_IDLE_LIMIT_SECONDS
    assert 0 < int(dockerfile_env()["UVICORN_WS_PING_INTERVAL"]) < CLOUDFLARE_IDLE_LIMIT_SECONDS


def test_dockerfile_settings_produce_a_pinging_protocol():
    """以 Dockerfile 的設定建立 uvicorn 實際使用的 protocol，確認它真的帶著 ping 間隔與逾時。"""
    env = dockerfile_env()
    interval, timeout = int(env["UVICORN_WS_PING_INTERVAL"]), int(env["UVICORN_WS_PING_TIMEOUT"])
    config = Config(lambda *_: None, ws=env["UVICORN_WS"], ws_ping_interval=interval, ws_ping_timeout=timeout)
    config.load()

    async def build():   # protocol 建構時需要執行中的 event loop
        return config.ws_protocol_class(config=config, server_state=ServerState(), app_state={})

    protocol = asyncio.run(build())

    assert (protocol.ping_interval, protocol.ping_timeout) == (interval, timeout)
