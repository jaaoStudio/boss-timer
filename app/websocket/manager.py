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

    def get_total_connections(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logging.info(f"New connection accepted. Total connections: {self.get_total_connections()}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
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
        if room_id in self.room_subscriptions:
            message_str = json.dumps(message, default=str)
            # Create a list of tasks for sending messages
            tasks = [
                conn.send_text(message_str) for conn in self.room_subscriptions[room_id]
            ]
            # Run all send tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logging.error(f"Error sending message to room {room_id}: {result}")

    async def broadcast_to_all(self, message: dict):
        """Broadcasts a message to all connected WebSocket clients."""
        if not self.active_connections:
            return

        message_str = json.dumps(message, default=str)
        tasks = [conn.send_text(message_str) for conn in self.active_connections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logging.error(f"Error broadcasting to all connections: {result}")

    def get_room_user_count(self, room_id: str) -> int:
        return len(self.room_subscriptions.get(room_id, set()))

    async def broadcast_user_count(self, room_id: str):
        count = self.get_room_user_count(room_id)
        await self.broadcast_to_room(room_id, {"type": "user_count_update", "count": count})
        logging.info(f"Broadcasted user count ({count}) for room {room_id}.")