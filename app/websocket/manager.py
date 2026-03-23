from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        # User-level personal notification sockets
        self.active_connections: Dict[str, WebSocket] = {}

        # Chat connections
        self.booking_connections: Dict[int, List[WebSocket]] = {}

        # Organizer notifications
        self.organizer_connections: Dict[int, WebSocket] = {}

        # NGO notifications
        self.ngo_connections: Dict[int, WebSocket] = {}

        # Surplus chat rooms: request_id -> list of websockets
        self.chat_rooms: Dict[int, List[WebSocket]] = {}

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
        self.active_connections[str(organizer_id)] = websocket
        self.organizer_connections[organizer_id] = websocket

    def disconnect_organizer(self, organizer_id: int):

        self.active_connections.pop(str(organizer_id), None)
        self.organizer_connections.pop(organizer_id, None)

    async def notify_organizer(self, organizer_id: int, message: dict):

        ws = self.organizer_connections.get(organizer_id)

        if ws:
            await ws.send_json(message)

    # ---------------- NGO ----------------

    async def connect_ngo(self, ngo_id: int, websocket: WebSocket):

        await websocket.accept()
        self.active_connections[str(ngo_id)] = websocket
        self.ngo_connections[ngo_id] = websocket

    def disconnect_ngo(self, ngo_id: int):

        self.active_connections.pop(str(ngo_id), None)
        self.ngo_connections.pop(ngo_id, None)

    async def notify_ngo(self, ngo_id: int, message: dict):

        ws = self.ngo_connections.get(ngo_id)

        if ws:
            await ws.send_json(message)
        else:
            print("NGO NOT CONNECTED:", ngo_id)

    # ---------------- SURPLUS CHAT ----------------

    async def connect_chat(self, request_id: int, websocket: WebSocket):

        await websocket.accept()

        if request_id not in self.chat_rooms:
            self.chat_rooms[request_id] = []

        self.chat_rooms[request_id].append(websocket)

    async def disconnect_chat(self, request_id: int, websocket: WebSocket):

        if request_id in self.chat_rooms:
            if websocket in self.chat_rooms[request_id]:
                self.chat_rooms[request_id].remove(websocket)

    async def broadcast_chat(self, request_id: int, message: dict):

        if request_id in self.chat_rooms:
            for connection in list(self.chat_rooms[request_id]):
                await connection.send_json(message)

    # ---------------- PERSONAL ----------------

    async def send_personal_message(self, user_id: str, message: dict):
        connection = self.active_connections.get(user_id)

        if connection:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Failed to send message to {user_id}:", e)
        else:
            print(f"User {user_id} not connected")


manager = ConnectionManager()