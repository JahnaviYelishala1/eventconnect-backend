from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List
from app.database import get_db
from app.models.chat_message import ChatMessage
from app.models.event_booking import EventBooking
from app.models.user import User
from app.models.caterer import Caterer
from app.utils.auth import ensure_db_user, get_current_user, verify_firebase_token
import json

router = APIRouter(prefix="/api", tags=["Chat"])


# ==========================================================
# Connection Manager
# ==========================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, booking_id: int, websocket: WebSocket):
        await websocket.accept()
        if booking_id not in self.active_connections:
            self.active_connections[booking_id] = []
        self.active_connections[booking_id].append(websocket)

    def disconnect(self, booking_id: int, websocket: WebSocket):
        if booking_id in self.active_connections and websocket in self.active_connections[booking_id]:
            self.active_connections[booking_id].remove(websocket)

    async def broadcast(self, booking_id: int, message: dict):
        if booking_id in self.active_connections:
            for connection in list(self.active_connections[booking_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(booking_id, connection)


manager = ConnectionManager()


# ==========================================================
# WebSocket Chat Endpoint
# ==========================================================

@router.websocket("/ws/chat/{booking_id}")
async def chat_websocket(
    websocket: WebSocket,
    booking_id: int,
    db: Session = Depends(get_db),
):
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    # Support both raw token and "Bearer <token>" query param formats.
    token = token.strip()
    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "", 1).strip()

    try:
        user_data = verify_firebase_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Keep websocket auth behavior consistent with HTTP routes:
    # create/link DB user from Firebase token if needed.
    db_user = ensure_db_user(user_data, db)

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        await websocket.close(code=1008, reason="Booking not found")
        return

    # Only booking organizer or assigned caterer can access this chat.
    booking_caterer = db.query(Caterer).filter(
        Caterer.id == booking.caterer_id
    ).first()

    is_organizer = db_user.id == booking.organizer_id
    is_assigned_caterer = bool(
        booking_caterer and booking_caterer.user_id == db_user.id
    )

    if not (is_organizer or is_assigned_caterer):
        await websocket.close(code=1008, reason="Not a participant")
        return

    await manager.connect(booking_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                json_data = json.loads(data)
            except json.JSONDecodeError:
                continue

            message_text = json_data.get("message")

            if not message_text:
                continue

            chat = ChatMessage(
                booking_id=booking_id,
                sender_id=db_user.id,
                message=message_text
            )

            db.add(chat)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue

            await manager.broadcast(
                booking_id,
                {
                    "sender_id": db_user.id,
                    "message": message_text,
                    "timestamp": chat.timestamp.isoformat()
                }
            )

    except WebSocketDisconnect:
        manager.disconnect(booking_id, websocket)


# ==========================================================
# Chat History Endpoint
# ==========================================================

@router.get("/chat/{booking_id}")
def get_chat_history(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=403, detail="Unauthorized")

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Same participant validation for history
    if db_user.id == booking.organizer_id:
        pass
    else:
        caterer = db.query(Caterer).filter(
            Caterer.user_id == db_user.id
        ).first()

        if not caterer or caterer.id != booking.caterer_id:
            raise HTTPException(status_code=403, detail="Not allowed")

    messages = db.query(ChatMessage).filter(
        ChatMessage.booking_id == booking_id
    ).order_by(ChatMessage.timestamp.asc()).all()

    return [
        {
            "sender_id": m.sender_id,
            "message": m.message,
            "timestamp": m.timestamp.isoformat()
        }
        for m in messages
    ]
