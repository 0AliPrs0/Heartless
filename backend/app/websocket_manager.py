from typing import List, Dict, Any
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[Dict[str, Any]]] = {}

    async def connect(self, websocket: WebSocket, game_id: int, user_id: int):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        
        # Avoid duplicate connections for the same user
        if not any(conn['user_id'] == user_id for conn in self.active_connections[game_id]):
            self.active_connections[game_id].append({"ws": websocket, "user_id": user_id})

    def disconnect(self, game_id: int, user_id: int):
        if game_id in self.active_connections:
            self.active_connections[game_id] = [
                conn for conn in self.active_connections[game_id]
                if conn["user_id"] != user_id
            ]
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except (WebSocketDisconnect, RuntimeError):
            print(f"Failed to send personal message: Client is disconnected.")

    async def broadcast(self, message: str, game_id: int):
        if game_id in self.active_connections:
            # Iterate over a copy of the list to safely modify during iteration
            for connection in self.active_connections[game_id][:]:
                try:
                    await connection["ws"].send_text(message)
                except (WebSocketDisconnect, RuntimeError):
                    print(f"Client {connection['user_id']} disconnected. Removing from active connections.")
                    self.disconnect(game_id, connection['user_id'])
    
    def get_websocket(self, game_id: int, user_id: int) -> WebSocket | None:
        if game_id in self.active_connections:
            for conn in self.active_connections[game_id]:
                if conn["user_id"] == user_id:
                    return conn["ws"]
        return None
