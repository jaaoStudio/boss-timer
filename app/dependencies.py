# app/dependencies.py
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.exceptions import WebSocketException
from jose import JWTError, jwt
from app.config import settings
import logging
from app.websocket.manager import ConnectionManager

_connection_manager = ConnectionManager()

def get_connection_manager() -> ConnectionManager:
    return _connection_manager

async def get_current_user_from_ws(websocket: WebSocket) -> str:
    """
    Extracts and validates JWT from WebSocket query parameters.
    """
    token = websocket.query_params.get("token")
    print(f"WebSocket token: {token}")

    if token is None:
        logging.error("WebSocket connection rejected: No token provided")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="No token provided")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            logging.error("WebSocket connection rejected: Invalid token payload")
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")

        logging.info(f"WebSocket authentication successful for user: {user_id}")
        return user_id

    except JWTError as e:
        logging.error(f"WebSocket JWT validation failed: {e}")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
    except Exception as e:
        logging.error(f"WebSocket authentication error: {e}")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")