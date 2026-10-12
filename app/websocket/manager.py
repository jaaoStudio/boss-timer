# app/websocket/manager.py
import json
import logging
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
from collections import Counter, defaultdict

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
        personal_key, ceiling_key = keys
        if self._connection_counts[personal_key] >= max_personal:
            return False
        if ceiling_key != personal_key and self._connection_counts[ceiling_key] >= max_ceiling:
            return False
        reserved = {personal_key, ceiling_key}
        self._connection_keys[websocket] = reserved
        self._connection_counts.update(reserved)
        return True

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
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
        message_str = json.dumps(message, default=str)
        connections = list(self.room_subscriptions[room_id])
        tasks = [conn.send_text(message_str) for conn in connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        dead = [conn for conn, result in zip(connections, results) if isinstance(result, Exception)]
        for conn in dead:
            logging.warning(f"Dead connection detected in room {room_id}, removing.")
            self.disconnect(conn)

    async def broadcast_to_all(self, message: dict):
        """Broadcasts a message to all connected WebSocket clients."""
        if not self.active_connections:
            return

        message_str = json.dumps(message, default=str)
        connections = list(self.active_connections)
        tasks = [conn.send_text(message_str) for conn in connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        dead = [conn for conn, result in zip(connections, results) if isinstance(result, Exception)]
        for conn in dead:
            logging.warning(f"Dead connection detected during broadcast_to_all, removing.")
            self.disconnect(conn)

    def get_room_user_count(self, room_id: str) -> int:
        return len(self.room_subscriptions.get(room_id, set()))

    async def broadcast_user_count(self, room_id: str):
        count = self.get_room_user_count(room_id)
        await self.broadcast_to_room(room_id, {"type": "user_count_update", "count": count})
        logging.info(f"Broadcasted user count ({count}) for room {room_id}.")