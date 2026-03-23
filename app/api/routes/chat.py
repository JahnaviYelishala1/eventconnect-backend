import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from openai import OpenAI

from app.database import SessionLocal, get_db
from app.models.caterer import Caterer
from app.models.chat_message import ChatMessage
from app.models.event_booking import EventBooking
from app.models.ngo import NGO
from app.models.surplus_request import SurplusRequest
from app.models.user import User
from app.utils.auth import get_current_user, verify_firebase_token
from app.utils.notifications import send_push_notification
from app.websocket.manager import manager
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


def call_llm(message: str) -> str:
    """
    Call OpenAI GPT-4o-mini for general catering queries.
    
    Args:
        message: User message text
    
    Returns:
        AI-generated response from GPT-4o-mini
    """
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful catering assistant. Help users with questions about food orders, dietary requirements, customization options, and delivery. Keep responses concise and friendly."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error(f"LLM call failed: {str(exc)}")
        return "I'm having trouble processing your request. Please try again later or contact support."


def detect_intent(message: str) -> str:
    """
    Detect user intent from message.
    
    Args:
        message: User message text
    
    Returns:
        Intent type: "cancel_order", "check_status", "refund", or "general"
    """
    msg = message.lower()

    if "cancel" in msg:
        return "cancel_order"
    elif "status" in msg or "progress" in msg:
        return "check_status"
    elif "refund" in msg:
        return "refund"
    else:
        return "general"


@router.websocket("/ws/{room_id}")
async def chat_socket(websocket: WebSocket, room_id: int):

    db = SessionLocal()

    token = websocket.query_params.get("token")
    chat_type = websocket.query_params.get("chat_type", "request")

    logger.info(
        "Chat WS connection attempt room_id=%s chat_type=%s has_token=%s",
        room_id,
        chat_type,
        bool(token),
    )

    if not token:
        logger.warning("Chat WS rejected room_id=%s chat_type=%s reason=missing_token", room_id, chat_type)
        await websocket.close(code=1008)
        db.close()
        return

    token = token.strip()
    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "", 1).strip()

    try:
        user_data = verify_firebase_token(token)
    except Exception as exc:
        logger.warning(
            "Chat WS rejected room_id=%s chat_type=%s reason=invalid_token error=%s",
            room_id,
            chat_type,
            str(exc),
        )
        await websocket.close(code=1008)
        db.close()
        return

    db_user = db.query(User).filter(
        User.firebase_uid == user_data["uid"]
    ).first()

    if not db_user:
        logger.warning(
            "Chat WS rejected room_id=%s chat_type=%s reason=user_not_found firebase_uid=%s",
            room_id,
            chat_type,
            user_data.get("uid"),
        )
        await websocket.close(code=1008)
        db.close()
        return

    # ========================================
    # DETERMINE CHAT TYPE AND AUTHORIZE
    # ========================================
    is_participant = False
    sender_role = None
    is_organizer = False
    is_caterer = False

    if chat_type == "booking":
        # ========== BOOKING CHAT ==========
        booking = db.query(EventBooking).filter(
            EventBooking.id == room_id
        ).first()

        if not booking:
            logger.warning("Chat WS rejected room_id=%s chat_type=booking reason=booking_not_found", room_id)
            await websocket.close(code=1008)
            db.close()
            return

        is_organizer = db_user.id == booking.organizer_id

        caterer = db.query(Caterer).filter(
            Caterer.user_id == db_user.id
        ).first()
        is_caterer = bool(caterer and caterer.id == booking.caterer_id)

        if not (is_organizer or is_caterer):
            logger.warning(
                "Chat WS rejected room_id=%s chat_type=booking user_id=%s reason=not_participant",
                room_id,
                db_user.id,
            )
            await websocket.close(code=1008)
            db.close()
            return

        is_participant = True
        sender_role = "event_organizer" if is_organizer else "caterer"
        entity = booking

    else:
        # ========== REQUEST CHAT (DEFAULT) ==========
        request = db.query(SurplusRequest).filter(
            SurplusRequest.id == room_id
        ).first()

        if not request:
            logger.warning("Chat WS rejected room_id=%s chat_type=request reason=request_not_found", room_id)
            await websocket.close(code=1008)
            db.close()
            return

        ngo = db.query(NGO).filter(
            NGO.firebase_uid == db_user.firebase_uid
        ).first()

        is_organizer = db_user.id == request.organizer_id
        is_accepted_ngo = bool(ngo and request.accepted_by_ngo == ngo.id)

        if not (is_organizer or is_accepted_ngo):
            logger.warning(
                "Chat WS rejected room_id=%s chat_type=request user_id=%s reason=not_participant",
                room_id,
                db_user.id,
            )
            await websocket.close(code=1008)
            db.close()
            return

        is_participant = True
        sender_role = "ngo" if is_accepted_ngo else "event_organizer"
        entity = request

    if not is_participant:
        logger.warning("Chat WS rejected room_id=%s chat_type=%s reason=not_authorized", room_id, chat_type)
        await websocket.close(code=1008)
        db.close()
        return

    await manager.connect_chat(room_id, websocket)
    logger.info(
        "Chat WS connected room_id=%s chat_type=%s user_id=%s role=%s sender_role=%s is_organizer=%s is_caterer=%s",
        room_id,
        chat_type,
        db_user.id,
        db_user.role,
        sender_role,
        is_organizer,
        is_caterer,
    )
    logger.info("WS CONNECTED user=%s room_id=%s chat_type=%s", db_user.id, room_id, chat_type)

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                logger.info(
                    "Chat WS disconnected room_id=%s chat_type=%s user_id=%s",
                    room_id,
                    chat_type,
                    db_user.id,
                )
                break
            except Exception as exc:
                logger.warning(
                    "Chat WS invalid_json room_id=%s chat_type=%s user_id=%s error=%s",
                    room_id,
                    chat_type,
                    db_user.id,
                    str(exc),
                )
                await websocket.send_json(
                    {
                        "type": "chat_error",
                        "error": "Invalid JSON payload",
                    }
                )
                continue

            logger.info(
                "Chat WS incoming room_id=%s chat_type=%s user_id=%s payload=%s",
                room_id,
                chat_type,
                db_user.id,
                data,
            )

            if not isinstance(data, dict):
                logger.warning(
                    "Chat WS invalid_payload room_id=%s chat_type=%s user_id=%s reason=non_object",
                    room_id,
                    chat_type,
                    db_user.id,
                )
                await websocket.send_json(
                    {
                        "type": "chat_error",
                        "error": "Payload must be a JSON object",
                    }
                )
                continue

            message_text = data.get("message")
            if not isinstance(message_text, str) or not message_text.strip():
                logger.warning(
                    "Chat WS invalid_payload room_id=%s chat_type=%s user_id=%s reason=missing_message",
                    room_id,
                    chat_type,
                    db_user.id,
                )
                continue

            normalized_message = message_text.strip()
            logger.info(
                "WS MESSAGE room_id=%s chat_type=%s user_id=%s sender_role=%s message=%s",
                room_id,
                chat_type,
                db_user.id,
                sender_role,
                normalized_message,
            )

            # ========== STORE MESSAGE WITH CORRECT ID ==========
            if chat_type == "booking":
                msg = ChatMessage(
                    booking_id=room_id,
                    sender_id=db_user.id,
                    sender_role=sender_role,
                    message=normalized_message,
                )
            else:
                msg = ChatMessage(
                    request_id=room_id,
                    sender_id=db_user.id,
                    sender_role=sender_role,
                    message=normalized_message,
                )

            db.add(msg)
            try:
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.exception(
                    "Chat WS persist_failed room_id=%s chat_type=%s user_id=%s error=%s",
                    room_id,
                    chat_type,
                    db_user.id,
                    str(exc),
                )
                continue

            # ✅ SEND PUSH NOTIFICATION
            try:
                if chat_type == "booking":
                    booking_entity = db.query(EventBooking).filter(EventBooking.id == room_id).first()
                    if booking_entity:
                        if sender_role == "event_organizer":
                            caterer_user = db.query(User).filter(
                                User.id == db.query(Caterer).filter(Caterer.id == booking_entity.caterer_id).first().user_id
                            ).first() if db.query(Caterer).filter(Caterer.id == booking_entity.caterer_id).first() else None
                            if caterer_user and caterer_user.fcm_token:
                                send_push_notification(
                                    caterer_user.fcm_token,
                                    "New Message",
                                    normalized_message,
                                    data={"room_id": str(room_id), "chat_type": "booking", "sender_role": "event_organizer"}
                                )
                                logger.info(
                                    "Chat WS notification_sent_to_caterer room_id=%s",
                                    room_id,
                                )
                        else:
                            organizer_user = db.query(User).filter(User.id == booking_entity.organizer_id).first()
                            if organizer_user and organizer_user.fcm_token:
                                send_push_notification(
                                    organizer_user.fcm_token,
                                    "New Message",
                                    normalized_message,
                                    data={"room_id": str(room_id), "chat_type": "booking", "sender_role": "caterer"}
                                )
                                logger.info(
                                    "Chat WS notification_sent_to_organizer room_id=%s",
                                    room_id,
                                )
                else:
                    # REQUEST CHAT
                    request_entity = db.query(SurplusRequest).filter(SurplusRequest.id == room_id).first()
                    if request_entity:
                        if sender_role == "ngo":
                            organizer_user = db.query(User).filter(
                                User.id == request_entity.organizer_id
                            ).first()
                            if organizer_user and organizer_user.fcm_token:
                                send_push_notification(
                                    organizer_user.fcm_token,
                                    "New Message",
                                    normalized_message,
                                    data={"request_id": str(room_id), "sender_role": "ngo"}
                                )
                                logger.info(
                                    "Chat WS notification_sent_to_organizer room_id=%s",
                                    room_id,
                                )
                        elif request_entity.accepted_by_ngo:
                            ngo_obj = db.query(NGO).filter(NGO.id == request_entity.accepted_by_ngo).first()
                            if ngo_obj:
                                ngo_user = db.query(User).filter(
                                    User.firebase_uid == ngo_obj.firebase_uid
                                ).first()
                                if ngo_user and ngo_user.fcm_token:
                                    send_push_notification(
                                        ngo_user.fcm_token,
                                        "New Message",
                                        normalized_message,
                                        data={"request_id": str(room_id), "sender_role": "event_organizer"}
                                    )
                                    logger.info(
                                        "Chat WS notification_sent_to_ngo room_id=%s",
                                        room_id,
                                    )
            except Exception as exc:
                logger.warning(
                    "Chat WS push_notification_failed room_id=%s user_id=%s error=%s",
                    room_id,
                    db_user.id,
                    str(exc),
                )

            outbound_payload = {
                "type": "chat_message",
                "room_id": room_id,
                "chat_type": chat_type,
                "sender_id": db_user.id,
                "message": normalized_message,
                "sender_role": sender_role,
                "timestamp": msg.timestamp.isoformat(),
            }

            try:
                await manager.broadcast_chat(room_id, outbound_payload)
                logger.info(
                    "Chat WS broadcast_ok room_id=%s chat_type=%s user_id=%s role=%s",
                    room_id,
                    chat_type,
                    db_user.id,
                    sender_role,
                )
                logger.info("WS BROADCAST room_id=%s user_id=%s", room_id, db_user.id)
            except Exception as exc:
                logger.warning(
                    "Chat WS broadcast_failed room_id=%s user_id=%s error=%s",
                    room_id,
                    db_user.id,
                    str(exc),
                )

            try:
                if chat_type == "booking":
                    booking_entity = db.query(EventBooking).filter(EventBooking.id == room_id).first()
                    if booking_entity:
                        if sender_role == "event_organizer":
                            await manager.notify_organizer(booking_entity.organizer_id, outbound_payload)
                            logger.info(
                                "Chat WS routed_to_organizer room_id=%s organizer_id=%s",
                                room_id,
                                booking_entity.organizer_id,
                            )
                        else:
                            caterer_user = db.query(Caterer).filter(Caterer.id == booking_entity.caterer_id).first()
                            if caterer_user:
                                await manager.notify_organizer(caterer_user.user_id, outbound_payload)
                                logger.info(
                                    "Chat WS routed_to_caterer room_id=%s caterer_user_id=%s",
                                    room_id,
                                    caterer_user.user_id,
                                )
                else:
                    # REQUEST CHAT
                    request_entity = db.query(SurplusRequest).filter(SurplusRequest.id == room_id).first()
                    if request_entity:
                        if sender_role == "ngo":
                            await manager.notify_organizer(request_entity.organizer_id, outbound_payload)
                            logger.info(
                                "Chat WS routed_to_organizer room_id=%s organizer_user_id=%s",
                                room_id,
                                request_entity.organizer_id,
                            )
                        elif request_entity.accepted_by_ngo:
                            await manager.notify_ngo(request_entity.accepted_by_ngo, outbound_payload)
                            logger.info(
                                "Chat WS routed_to_ngo room_id=%s ngo_id=%s",
                                room_id,
                                request_entity.accepted_by_ngo,
                            )
            except Exception as exc:
                logger.warning(
                    "Chat WS route_failed room_id=%s user_id=%s error=%s",
                    room_id,
                    db_user.id,
                    str(exc),
                )

    except Exception as exc:
        logger.exception(
            "Chat WS unhandled_error room_id=%s chat_type=%s user_id=%s error=%s",
            room_id,
            chat_type,
            db_user.id,
            str(exc),
        )

    finally:
        await manager.disconnect_chat(room_id, websocket)
        logger.info("Chat WS closed room_id=%s chat_type=%s user_id=%s", room_id, chat_type, db_user.id)
        db.close()


@router.get("/{room_id}")
def get_chat_history(
    room_id: int,
    chat_type: Literal["booking", "request", "auto"] = Query("auto"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=403, detail="Unauthorized")

    booking = db.query(EventBooking).filter(
        EventBooking.id == room_id
    ).first()

    request = db.query(SurplusRequest).filter(
        SurplusRequest.id == room_id
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

    is_request_participant = False
    if request:
        ngo = db.query(NGO).filter(
            NGO.firebase_uid == db_user.firebase_uid
        ).first()

        is_request_organizer = db_user.id == request.organizer_id
        is_accepted_ngo = bool(ngo and request.accepted_by_ngo == ngo.id)
        is_request_participant = bool(is_request_organizer or is_accepted_ngo)

    if chat_type == "request":
        if not request:
            raise HTTPException(status_code=404, detail="Request room not found")
        if not is_request_participant:
            raise HTTPException(status_code=403, detail="Not allowed for request chat")

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.request_id == room_id)
            .order_by(ChatMessage.timestamp)
            .all()
        )
    elif chat_type == "auto":
        if is_request_participant:
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.request_id == room_id)
                .order_by(ChatMessage.timestamp)
                .all()
            )
        elif is_booking_participant:
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.booking_id == room_id)
                .order_by(ChatMessage.timestamp)
                .all()
            )
        elif request or booking:
            raise HTTPException(status_code=403, detail="Not allowed for this chat")
        else:
            raise HTTPException(status_code=404, detail="Chat room not found")
    else:
        if not booking:
            raise HTTPException(status_code=404, detail="Booking room not found")
        if not is_booking_participant:
            raise HTTPException(status_code=403, detail="Not allowed for booking chat")

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.booking_id == room_id)
            .order_by(ChatMessage.timestamp)
            .all()
        )

    return messages


@router.post("/ai-assistant", response_model=ChatResponse)
def ai_assistant(
    req: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    AI assistant endpoint for handling catering booking queries.
    
    Detects user intent (cancel, status, refund, or general) and responds accordingly.
    """
    intent = detect_intent(req.message)

    booking = db.query(EventBooking).filter(
        EventBooking.id == req.booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if intent == "check_status":
        return ChatResponse(
            reply=f"Your order is currently '{booking.status}'."
        )

    elif intent == "cancel_order":
        booking.status = "CANCELLED"
        db.commit()
        return ChatResponse(
            reply="Your order has been cancelled successfully."
        )

    elif intent == "refund":
        # Dummy logic (replace with Stripe if needed)
        return ChatResponse(
            reply="Your refund request has been initiated."
        )

    else:
        # Use LLM for general queries
        llm_response = call_llm(req.message)
        return ChatResponse(reply=llm_response)