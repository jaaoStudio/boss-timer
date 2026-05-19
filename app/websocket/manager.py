# app/websocket/manager.py
import json
import logging
import asyncio
from typing import Dict, Set, Optional, List
from fastapi import WebSocket
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        # A set of all active connections
        self.active_connections: Set[WebSocket] = set()
        # A dictionary to map room_id to a set of subscribed WebSockets
        self.room_subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        # A dictionary to map WebSocket to its subscribed room_id
        self.socket_to_room: Dict[WebSocket, str] = {}
        # A dictionary to map WebSocket to its user_id
        self.socket_to_user: Dict[WebSocket, int] = {}

    def get_total_connections(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        if user_id:
            self.socket_to_user[websocket] = user_id
        logging.info(f"New connection accepted. User ID: {user_id}. Total connections: {self.get_total_connections()}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.socket_to_user.pop(websocket, None) # Remove user mapping on disconnect
        logging.info(f"Connection closed. Total connections: {self.get_total_connections()}")
        # Also remove from any room subscriptions
        if websocket in self.socket_to_room:
            room_id = self.socket_to_room[websocket]
            self.room_subscriptions[room_id].discard(websocket)
            if not self.room_subscriptions[room_id]:
                del self.room_subscriptions[room_id]
            del self.socket_to_room[websocket]
            logging.info(f"Connection removed from room {room_id}")

    def update_user_id(self, websocket: WebSocket, user_id: Optional[int]):
        if user_id is not None:
            self.socket_to_user[websocket] = user_id
            logging.info(f"Updated user ID for connection to {user_id}")
        else:
            if websocket in self.socket_to_user:
                del self.socket_to_user[websocket]
                logging.info(f"Removed user ID for connection")

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