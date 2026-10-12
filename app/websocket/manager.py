# app/websocket/manager.py
import json
import logging
import asyncio
from typing import Dict, Set, Optional, List
from fastapi import WebSocket
from collections import Counter, defaultdict

from app.utils.identity import Identity

class ConnectionManager:
    def __init__(self):
        # A set of all active connections
        self.active_connections: Set[WebSocket] = set()
        # A dictionary to map room_id to a set of subscribed WebSockets
        self.room_subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        # A dictionary to map WebSocket to its subscribed room_id
        self.socket_to_room: Dict[WebSocket, str] = {}
        # 連線目前的身分（伺服器端決定，見 docs/adr/0007）；登入 / 登出會在連線中途切換
        self.socket_identity: Dict[WebSocket, Identity] = {}
        # 登出（deauthenticate）時退回的身分：握手時 cookie 裡的匿名身分，沒有則為 none
        self._fallback_identity: Dict[WebSocket, Identity] = {}
        # 同時連線數：連線建立時計入的 key（個人、IP 天花板），斷線時以同一組 key 扣回
        self._connection_keys: Dict[WebSocket, Set[str]] = {}
        self._connection_counts: Counter = Counter()

    def get_total_connections(self) -> int:
        return len(self.active_connections)

    def has_capacity(self, personal_key: str, ceiling_key: str, max_personal: int, max_ceiling: int) -> bool:
        """新連線是否在同時連線數上限內（登入者的兩個 key 相同，只受個人上限限制）。"""
        if self._connection_counts[personal_key] >= max_personal:
            return False
        return ceiling_key == personal_key or self._connection_counts[ceiling_key] < max_ceiling

    async def connect(self, websocket: WebSocket, identity: Identity, fallback_identity: Identity, connection_keys: Set[str]):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.socket_identity[websocket] = identity
        self._fallback_identity[websocket] = fallback_identity
        self._connection_keys[websocket] = connection_keys
        self._connection_counts.update(connection_keys)
        logging.info(f"New connection accepted. Identity: {identity.kind}. Total connections: {self.get_total_connections()}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.socket_identity.pop(websocket, None)
        self._fallback_identity.pop(websocket, None)
        self._connection_counts.subtract(self._connection_keys.pop(websocket, set()))
        self._connection_counts += Counter()  # 移除歸零的 key，避免計數表無限長大
        logging.info(f"Connection closed. Total connections: {self.get_total_connections()}")
        # Also remove from any room subscriptions
        if websocket in self.socket_to_room:
            room_id = self.socket_to_room[websocket]
            self.room_subscriptions[room_id].discard(websocket)
            if not self.room_subscriptions[room_id]:
                del self.room_subscriptions[room_id]
            del self.socket_to_room[websocket]
            logging.info(f"Connection removed from room {room_id}")

    def set_identity(self, websocket: WebSocket, identity: Identity):
        """登入（authenticate）後切換為登入身分。"""
        self.socket_identity[websocket] = identity

    def reset_identity(self, websocket: WebSocket):
        """登出（deauthenticate）後退回握手時的匿名身分。"""
        self.socket_identity[websocket] = self._fallback_identity.get(websocket, Identity("none"))

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