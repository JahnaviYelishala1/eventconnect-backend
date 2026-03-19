from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):

        # Chat connections
        self.booking_connections: Dict[int, List[WebSocket]] = {}

        # Organizer notifications
        self.organizer_connections: Dict[int, WebSocket] = {}

        # NGO notifications
        self.ngo_connections: Dict[int, WebSocket] = {}

    # ---------------- CHAT ----------------

    async def connect_booking(self, booking_id: int, websocket: WebSocket):

        if booking_id not in self.booking_connections:
            self.booking_connections[booking_id] = []

        self.booking_connections[booking_id].append(websocket)

    def disconnect_booking(self, booking_id: int, websocket: WebSocket):

        if booking_id in self.booking_connections:
            if websocket in self.booking_connections[booking_id]:
                self.booking_connections[booking_id].remove(websocket)

    async def broadcast_booking(self, booking_id: int, message: dict):

        if booking_id in self.booking_connections:
            for connection in list(self.booking_connections[booking_id]):
                await connection.send_json(message)

    # ---------------- ORGANIZER ----------------

    async def connect_organizer(self, organizer_id: int, websocket: WebSocket):

        await websocket.accept()
        self.organizer_connections[organizer_id] = websocket

    def disconnect_organizer(self, organizer_id: int):

        self.organizer_connections.pop(organizer_id, None)

    async def notify_organizer(self, organizer_id: int, message: dict):

        ws = self.organizer_connections.get(organizer_id)

        if ws:
            await ws.send_json(message)

    # ---------------- NGO ----------------

    async def connect_ngo(self, ngo_id: int, websocket: WebSocket):

        await websocket.accept()
        self.ngo_connections[ngo_id] = websocket

    def disconnect_ngo(self, ngo_id: int):

        self.ngo_connections.pop(ngo_id, None)

    async def notify_ngo(self, ngo_id: int, message: dict):

        ws = self.ngo_connections.get(ngo_id)

        if ws:
            await ws.send_json(message)


manager = ConnectionManager()