from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, booking_id: int, websocket: WebSocket):
        # ❌ REMOVE websocket.accept() from here
        if booking_id not in self.active_connections:
            self.active_connections[booking_id] = []

        self.active_connections[booking_id].append(websocket)

    def disconnect(self, booking_id: int, websocket: WebSocket):
        if booking_id in self.active_connections:
            if websocket in self.active_connections[booking_id]:
                self.active_connections[booking_id].remove(websocket)

    async def broadcast(self, booking_id: int, message: dict):
        if booking_id in self.active_connections:
            for connection in list(self.active_connections[booking_id]):
                await connection.send_json(message)


manager = ConnectionManager()