# app/websocket/manager.py

from typing import Dict
from fastapi import WebSocket

class ConnectionManager:

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()

        # If same user reconnects, replace old connection
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except:
                pass

        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)

        if not websocket:
            return

        try:
            await websocket.send_json(message)
        except:
            # Remove broken connection
            self.disconnect(user_id)

manager = ConnectionManager()