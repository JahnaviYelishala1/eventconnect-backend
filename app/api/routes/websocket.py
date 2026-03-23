import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.database import SessionLocal
from app.models.chat_message import ChatMessage
from app.websocket.manager import manager
from app.utils.auth import verify_firebase_token
from app.models.user import User
from app.models.event_booking import EventBooking
from app.models.surplus_request import SurplusRequest
from app.models.ngo import NGO
from app.models.caterer import Caterer

router = APIRouter()


@router.websocket("/ws/chat/{booking_id}")
@router.websocket("/api/ws/chat/{booking_id}")
async def chat_websocket(websocket: WebSocket, booking_id: int):
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008)
        return

    token = token.strip()
    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "", 1).strip()

    from app.database import SessionLocal
    db = SessionLocal()

    room_type = None

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

        is_booking_participant = False
        if booking:
            is_organizer = db_user.id == booking.organizer_id

            caterer = db.query(Caterer).filter(
                Caterer.user_id == db_user.id
            ).first()

            is_assigned_caterer = bool(
                caterer and caterer.id == booking.caterer_id
            )

            is_booking_participant = bool(is_organizer or is_assigned_caterer)

        request = db.query(SurplusRequest).filter(
            SurplusRequest.id == booking_id
        ).first()

        is_request_participant = False
        if request:
            is_request_organizer = db_user.id == request.organizer_id

            ngo = db.query(NGO).filter(
                NGO.firebase_uid == db_user.firebase_uid
            ).first()

            is_accepted_ngo = bool(
                ngo and request.accepted_by_ngo == ngo.id
            )

            is_request_participant = bool(is_request_organizer or is_accepted_ngo)

        # Prefer request room when both IDs exist and user is a participant there.
        if is_request_participant:
            room_type = "request"
            await manager.connect_chat(booking_id, websocket)
        elif is_booking_participant:
            room_type = "booking"
            await websocket.accept()
            await manager.connect_booking(booking_id, websocket)
        else:
            await websocket.close(code=1008)
            return

        while True:
            data = await websocket.receive_text()

            try:
                json_data = json.loads(data)
            except json.JSONDecodeError:
                continue

            message_text = json_data.get("message")

            if not message_text:
                continue

            sender_role = "ngo" if db_user.role == "ngo" else "event_organizer"

            if room_type == "request":
                chat = ChatMessage(
                    request_id=booking_id,
                    sender_id=db_user.id,
                    sender_role=sender_role,
                    message=message_text
                )
            else:
                chat = ChatMessage(
                    booking_id=booking_id,
                    sender_id=db_user.id,
                    sender_role=db_user.role or "user",
                    message=message_text
                )

            db.add(chat)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue

            if room_type == "request":
                await manager.broadcast_chat(
                    booking_id,
                    {
                        "type": "chat_message",
                        "sender_id": db_user.id,
                        "sender_role": sender_role,
                        "message": message_text,
                        "timestamp": chat.timestamp.isoformat()
                    }
                )
            else:
                await manager.broadcast_booking(
                    booking_id,
                    {
                        "sender_id": db_user.id,
                        "message": message_text,
                        "timestamp": chat.timestamp.isoformat()
                    }
                )

    except WebSocketDisconnect:
        pass

    finally:
        if room_type == "request":
            await manager.disconnect_chat(booking_id, websocket)
        elif room_type == "booking":
            manager.disconnect_booking(booking_id, websocket)
        db.close()