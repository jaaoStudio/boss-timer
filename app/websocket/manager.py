# app/websocket/manager.py
import json
import logging
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
from collections import Counter, defaultdict

# 伺服器心跳（ADR-0008，照 Socket.IO / engine.io v4）：每 HEARTBEAT_INTERVAL_SECONDS 對所有連線送 heartbeat，
# 用戶端超過「間隔 + HEARTBEAT_TIMEOUT_SECONDS」沒收到就視為斷線。兩個數字在連線時以 hello 告訴用戶端
HEARTBEAT_INTERVAL_SECONDS = 25
HEARTBEAT_TIMEOUT_SECONDS = 20
HELLO_MESSAGE = json.dumps({
    "type": "hello",
    "ping_interval": HEARTBEAT_INTERVAL_SECONDS,
    "ping_timeout": HEARTBEAT_TIMEOUT_SECONDS,
})
# 廣播時每條連線的送出上限：一條連線卡住（對方不讀、TCP 緩衝滿）時不拖住其他連線，否則心跳延遲會讓所有人同時逾時重連
SEND_TIMEOUT_SECONDS = 5

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
        # 第一則訊息：用戶端收到才啟動心跳逾時判斷（舊版後端不送，用戶端就不判斷）。
        # 送完才加入 active_connections，心跳才不會搶在 hello 前面
        await websocket.send_text(HELLO_MESSAGE)
        self.active_connections.add(websocket)
        logging.info(f"New connection accepted. Total connections: {self.get_total_connections()}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        for key in self._connection_keys.pop(websocket, ()):
            self._connection_counts[key] -= 1
            if self._connection_counts[key] <= 0:
                del self._connection_counts[key]
        logging.info(f"Connection closed. Total connections: {self.get_total_connections()}")
        # Also remove from any room subscriptions
        if websocket in self.socket_to_room:
            room_id = self.socket_to_room[websocket]
            self.room_subscriptions[room_id].discard(websocket)
            if not self.room_subscriptions[room_id]:
                del self.room_subscriptions[room_id]
            del self.socket_to_room[websocket]
            logging.info(f"Connection removed from room {room_id}")

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

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id not in self.room_subscriptions:
            return
        await self._send_all(list(self.room_subscriptions[room_id]), json.dumps(message, default=str))

    async def broadcast_to_all(self, message: dict):
        """Broadcasts a message to all connected WebSocket clients."""
        if not self.active_connections:
            return
        await self._send_all(list(self.active_connections), json.dumps(message, default=str))

    @staticmethod
    async def _send_all(connections: list[WebSocket], message_str: str):
        """
        同時送給多條連線，每條最多等 SEND_TIMEOUT_SECONDS。送不出去只記錄、不在這裡 disconnect：
        清理一律交給該連線 endpoint 的 finally（它會一併廣播房間人數）；連線已斷時 receive 會結束，
        卡住的連線由協定層 ping 逾時關閉。
        """
        results = await asyncio.gather(
            *(asyncio.wait_for(conn.send_text(message_str), SEND_TIMEOUT_SECONDS) for conn in connections),
            return_exceptions=True,
        )
        failed = sum(isinstance(result, BaseException) for result in results)
        if failed:
            logging.warning(f"Broadcast failed for {failed} of {len(connections)} connection(s).")

    def get_room_user_count(self, room_id: str) -> int:
        return len(self.room_subscriptions.get(room_id, set()))

    async def broadcast_user_count(self, room_id: str):
        count = self.get_room_user_count(room_id)
        await self.broadcast_to_room(room_id, {"type": "user_count_update", "count": count})
        logging.info(f"Broadcasted user count ({count}) for room {room_id}.")

    async def run_heartbeat(self, interval: float = HEARTBEAT_INTERVAL_SECONDS):
        """
        定時對所有連線送 heartbeat（一個全域 loop，不必每條連線一個 task），讓用戶端能偵測無聲中斷。
        伺服器端的死連線偵測靠 uvicorn 協定層 ping，勿以用戶端有沒有回應判斷生死（#43）。
        """
        while True:
            await asyncio.sleep(interval)
            try:
                await self.broadcast_to_all({"type": "heartbeat"})
            except Exception as e:
                logging.error(f"Heartbeat broadcast failed: {e}")
