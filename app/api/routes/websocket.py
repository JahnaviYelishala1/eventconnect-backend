import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.chat_message import ChatMessage
from app.websocket.manager import manager
from app.utils.auth import verify_firebase_token
from app.models.user import User
from app.models.event_booking import EventBooking 
from app.models.caterer import Caterer
 # make sure you have this model

router = APIRouter()


@router.websocket("/ws/chat/{booking_id}")
async def chat_websocket(websocket: WebSocket, booking_id: int):
    await websocket.accept()
    await manager.connect_booking(booking_id, websocket)

    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008)
        return

    from app.database import SessionLocal
    db = SessionLocal()

    try:
        user_data = verify_firebase_token(token)

        db_user = db.query(User).filter(
            User.firebase_uid == user_data["uid"]
        ).first()

        if not db_user:
            await websocket.close(code=1008)
            return

        booking = db.query(EventBooking).filter(
            EventBooking.id == booking_id
        ).first()

        if not booking:
            await websocket.close(code=1008)
            return

        is_organizer = db_user.id == booking.organizer_id

        caterer = db.query(Caterer).filter(
            Caterer.user_id == db_user.id
        ).first()

        is_assigned_caterer = bool(
            caterer and caterer.id == booking.caterer_id
        )

        if not (is_organizer or is_assigned_caterer):
            await websocket.close(code=1008)
            return

        await manager.connect_booking(booking_id, websocket)

        while True:
            data = await websocket.receive_text()

            json_data = json.loads(data)
            message_text = json_data.get("message")

            chat = ChatMessage(
                booking_id=booking_id,
                sender_id=db_user.id,
                message=message_text
            )

            db.add(chat)
            db.commit()

            await manager.broadcast_booking(
                booking_id,
                {
                    "sender_id": db_user.id,
                    "message": message_text,
                    "timestamp": chat.timestamp.isoformat()
                }
            )

    except WebSocketDisconnect:
        manager.disconnect_booking(booking_id, websocket)

    finally:
        db.close()