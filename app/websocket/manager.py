# app/websocket/manager.py
from anyio import from_thread
import json
import logging
import asyncio
from contextlib import suppress
from typing import Dict, Set
from fastapi import WebSocket
from collections import Counter, defaultdict

# 伺服器心跳（ADR-0008，照 Socket.IO / engine.io v4）：每 HEARTBEAT_INTERVAL_SECONDS 對所有連線送 heartbeat，
# 用戶端超過「間隔 + HEARTBEAT_TIMEOUT_SECONDS」沒收到就視為斷線。兩個數字在連線時以 hello 告訴用戶端
HEARTBEAT_INTERVAL_SECONDS = 25
HEARTBEAT_TIMEOUT_SECONDS = 20
HELLO_MESSAGE = {
    "type": "hello",
    "ping_interval": HEARTBEAT_INTERVAL_SECONDS,
    "ping_timeout": HEARTBEAT_TIMEOUT_SECONDS,
}
# 同一則訊息從開始送出算起這麼久還送不出去，就關閉連線。對應 engine.io 的 pingTimeout：對方不收時 ping 也送不到、
# 收不到 pong，時間一到就關閉。協定層 ping 要先寫進同一個塞滿的緩衝才開始計時，這種情況永遠不會逾時。
# 對方停止接收後約 90 秒內一定關閉：緩衝沒塞滿時協定層 ping 送得出去、收不到 pong，約 80 秒由協定層 ping 關閉；
# 緩衝塞滿時 ping 卡住，但下一則心跳（最晚 25 秒後）也會卡住，再 45 秒由這裡關閉。
# 只看伺服器送不送得出去，不看用戶端有沒有回應：凍結的背景分頁瀏覽器仍會先收下，極少被關閉（#43）；
# 活躍房間的分頁凍結數小時、緩衝塞滿時仍可能關閉，engine.io 在這種情況會更早關閉，我們接受
SEND_STALL_SECONDS = HEARTBEAT_INTERVAL_SECONDS + HEARTBEAT_TIMEOUT_SECONDS

class ConnectionManager:
    def __init__(self):
        # A set of all active connections
        self.active_connections: Set[WebSocket] = set()
        # A dictionary to map room_id to a set of subscribed WebSockets
        self.room_subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        # A dictionary to map WebSocket to its subscribed room_id
        self.socket_to_room: Dict[WebSocket, str] = {}
        # 同時連線數：握手時計入的 key（個人、IP 天花板），斷線時以同一組 key 扣回
        self._connection_keys: Dict[WebSocket, Set[str]] = {}
        self._connection_counts: Counter = Counter()
        # 送出佇列（照 engine.io 的 writeBuffer，ADR-0008）：每條連線一個佇列與一個寫出 task，
        # 送訊息只放進佇列、不等對方收，一條卡住的連線不會拖住廣播的呼叫端與其他連線
        self._outboxes: Dict[WebSocket, tuple[asyncio.Queue[str], asyncio.Task]] = {}

    def get_total_connections(self) -> int:
        return len(self.active_connections)

    def try_reserve(self, websocket: WebSocket, keys: tuple[str, str], max_personal: int, max_ceiling: int) -> bool:
        """
        在同時連線數上限內就計入並回傳 True。檢查與計入在同一步完成、中間沒有 await，
        大量同時握手時不會全部通過檢查。登入者的兩個 key 相同，只受個人上限限制。
        """
        # 個人與天花板分開計數：沒有身分時兩者都是 IP key，混在一起的話，
        # 個人上限會被同 IP 所有匿名連線的天花板計數吃掉
        personal_key, ceiling_key = keys
        personal, ceiling = f"personal:{personal_key}", f"ceiling:{ceiling_key}"
        if self._connection_counts[personal] >= max_personal:
            return False
        check_ceiling = ceiling_key != personal_key
        if check_ceiling and self._connection_counts[ceiling] >= max_ceiling:
            return False
        reserved = {personal, ceiling} if check_ceiling else {personal}
        self._connection_keys[websocket] = reserved
        self._connection_counts.update(reserved)
        return True

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        outbox: asyncio.Queue[str] = asyncio.Queue()
        self._outboxes[websocket] = (outbox, asyncio.create_task(self._write(websocket, outbox)))
        self.active_connections.add(websocket)
        # 第一則訊息：用戶端收到才啟動心跳逾時判斷（舊版後端不送，用戶端就不判斷）
        self.send(websocket, HELLO_MESSAGE)
        logging.info(f"New connection accepted. Total connections: {self.get_total_connections()}")

    def send(self, websocket: WebSocket, message: dict):
        """放進該連線的送出佇列，依放入順序送出；連線已結束就丟棄。"""
        self._enqueue(websocket, json.dumps(message, default=str))

    def _enqueue(self, websocket: WebSocket, text: str):
        if (entry := self._outboxes.get(websocket)) is not None:
            entry[0].put_nowait(text)

    async def _write(self, websocket: WebSocket, outbox: asyncio.Queue[str]):
        """
        依序送出佇列裡的訊息。送出失敗或超過 SEND_STALL_SECONDS 送不出去就關閉連線（照 engine.io 傳輸出錯即關閉），
        清理交給 endpoint 的 finally（會一併更新房間人數）。
        """
        try:
            while True:
                text = await outbox.get()
                async with asyncio.timeout(SEND_STALL_SECONDS):
                    await websocket.send_text(text)
        except Exception as e:
            logging.info(f"WebSocket send failed, closing: {e!r}")
            # 不再有人送出：之後的訊息直接丟棄，不留在沒人讀的佇列（房間資料留給 endpoint 清理）
            self._outboxes.pop(websocket, None)
            with suppress(Exception):   # 對方已斷線時 close 也會失敗，receive 一樣會結束
                await websocket.close()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if (entry := self._outboxes.pop(websocket, None)) is not None:
            entry[1].cancel()   # 停掉寫出 task，尚未送出的訊息隨連線丟棄
        for key in self._connection_keys.pop(websocket, ()):
            self._connection_counts[key] -= 1
            if self._connection_counts[key] <= 0:
                del self._connection_counts[key]
        logging.info(f"Connection closed. Total connections: {self.get_total_connections()}")
        self.unsubscribe_from_room(websocket)

    def subscribe_to_room(self, websocket: WebSocket, room_id: str):
        # Unsubscribe from any previous room first
        if websocket in self.socket_to_room:
            previous_room = self.socket_to_room[websocket]
            if previous_room != room_id:
                self.unsubscribe_from_room(websocket)

        self.room_subscriptions[room_id].add(websocket)
        self.socket_to_room[websocket] = room_id
        logging.info(f"Connection subscribed to room {room_id}")

    def unsubscribe_from_room(self, websocket: WebSocket):
        if websocket in self.socket_to_room:
            room_id = self.socket_to_room[websocket]
            self.room_subscriptions[room_id].discard(websocket)
            if not self.room_subscriptions[room_id]:
                del self.room_subscriptions[room_id]
            del self.socket_to_room[websocket]
            logging.info(f"Connection unsubscribed from room {room_id}")

    # 廣播只把訊息放進每條連線的送出佇列、不等待送出，呼叫端不會被慢的連線拖住
    async def broadcast_to_room(self, room_id: str, message: dict):
        self._enqueue_all(self.room_subscriptions.get(room_id, ()), message)

    def broadcast_to_room_from_thread(self, room_id: str, message: dict) -> None:
        """
        在 threadpool 裡執行的同步端點（def）要廣播時用：回到 event loop 上執行，manager 的狀態只在 event loop 上操作
        （送出佇列是 asyncio.Queue，不是 thread-safe，ADR-0010）
        """
        from_thread.run_sync(lambda: self._enqueue_all(self.room_subscriptions.get(room_id, ()), message))

    def broadcast_to_all_from_thread(self, message: dict) -> None:
        """同 broadcast_to_room_from_thread，廣播給所有連線"""
        from_thread.run_sync(lambda: self._enqueue_all(self.active_connections, message))

    async def broadcast_to_all(self, message: dict):
        """Broadcasts a message to all connected WebSocket clients."""
        self._enqueue_all(self.active_connections, message)

    def _enqueue_all(self, connections, message: dict):
        message_str = json.dumps(message, default=str)
        for conn in connections:
            self._enqueue(conn, message_str)

    def get_room_user_count(self, room_id: str) -> int:
        return len(self.room_subscriptions.get(room_id, set()))

    async def broadcast_user_count(self, room_id: str):
        count = self.get_room_user_count(room_id)
        await self.broadcast_to_room(room_id, {"type": "user_count_update", "count": count})
        logging.info(f"Broadcasted user count ({count}) for room {room_id}.")

    async def run_heartbeat(self, interval: float = HEARTBEAT_INTERVAL_SECONDS):
        """
        定時對所有連線送 heartbeat（一個全域 loop），讓用戶端能偵測無聲中斷。
        伺服器端的死連線偵測靠 uvicorn 協定層 ping 與 SEND_STALL_SECONDS，勿以用戶端有沒有回應判斷生死（#43）。
        """
        while True:
            await asyncio.sleep(interval)
            try:
                await self.broadcast_to_all({"type": "heartbeat"})
            except Exception as e:
                # 全站只有這一個心跳 task，勿讓例外結束它（否則所有用戶端都會逾時重連）
                logging.error(f"Heartbeat broadcast failed: {e}", exc_info=True)
