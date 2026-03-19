from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.websocket.manager import manager
from app.utils.auth import verify_firebase_token
from app.utils.distance import calculate_distance
from app.models.user import User
from app.models.ngo import NGO
from app.models.ngo_profile import NGOProfile
from app.models.surplus_request import SurplusRequest
from app.models.event import Event

router = APIRouter()


async def _send_open_nearby_alerts(db: Session, ngo_id: int, user_id: int):
    ngo_profile = (
        db.query(NGOProfile)
        .filter(NGOProfile.user_id == user_id)
        .first()
    )

    if (
        not ngo_profile
        or ngo_profile.latitude is None
        or ngo_profile.longitude is None
    ):
        return

    open_requests = (
        db.query(SurplusRequest, Event)
        .join(Event, Event.id == SurplusRequest.event_id)
        .filter(
            SurplusRequest.status == "OPEN",
            SurplusRequest.accepted_by_ngo.is_(None)
        )
        .order_by(SurplusRequest.created_at.desc())
        .limit(100)
        .all()
    )

    for request, event in open_requests:
        if request.latitude is None or request.longitude is None:
            continue

        distance = calculate_distance(
            ngo_profile.latitude,
            ngo_profile.longitude,
            request.latitude,
            request.longitude,
        )

        if distance > 30:
            continue

        await manager.notify_ngo(
            ngo_id,
            {
                "type": "surplus_food",
                "request_id": request.id,
                "event_name": event.event_name,
                "food_description": request.food_description,
                "description": request.food_description,
                "image_url": request.image_url,
                "distance": round(distance, 2),
                "latitude": request.latitude,
                "longitude": request.longitude,
            }
        )


@router.websocket("/ws/ngo")
async def ngo_websocket(websocket: WebSocket, token: str | None = None):

    db: Session = SessionLocal()
    ngo = None

    try:
        if not token:
            await websocket.close(code=1008)
            return

        normalized_token = token.strip()
        if normalized_token.startswith("Bearer "):
            normalized_token = normalized_token.replace("Bearer ", "", 1).strip()

        user_data = verify_firebase_token(normalized_token)

        db_user = db.query(User).filter(
            User.firebase_uid == user_data["uid"]
        ).first()

        if not db_user:
            await websocket.close()
            return

        if db_user.role != "ngo":
            await websocket.close()
            return

        ngo = db.query(NGO).filter(
            NGO.firebase_uid == user_data["uid"]
        ).first()

        if not ngo:
            await websocket.close()
            return

        await manager.connect_ngo(ngo.id, websocket)
        await _send_open_nearby_alerts(db, ngo.id, db_user.id)

        while True:
            await websocket.receive_text()

    except HTTPException:
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        if ngo:
            manager.disconnect_ngo(ngo.id)

    finally:
        db.close()