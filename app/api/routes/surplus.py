import logging
import requests

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.organizer import Organizer
from app.schemas.surplus import (
    SurplusAcceptedResponse,
    SurplusAlertResponse,
    SurplusCreate,
    SurplusNgoResponse,
)
from app.models.surplus_request import SurplusRequest
from app.models.event import Event
from app.models.event_location import EventLocation
from app.models.ngo import NGO
from app.models.ngo_profile import NGOProfile
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.notifications import send_push_notification
from app.websocket.manager import manager


router = APIRouter(prefix="/api/surplus", tags=["Surplus Food"])
logger = logging.getLogger(__name__)


def _get_ngo_contact_info(db: Session, ngo: NGO) -> tuple[str, str]:
    db_user = db.query(User).filter(User.firebase_uid == ngo.firebase_uid).first()
    profile = None

    if db_user:
        profile = (
            db.query(NGOProfile)
            .filter(NGOProfile.user_id == db_user.id)
            .first()
        )

    ngo_name = (profile.name if profile and profile.name else ngo.name) or ""
    phone = ""

    if profile and profile.phone:
        phone = profile.phone
    elif db_user and db_user.phone:
        phone = db_user.phone

    return ngo_name, phone

@router.post("/send-alert", response_model=SurplusAlertResponse)
async def send_surplus_alert(
    data: SurplusCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(status_code=403, detail="Only organizers allowed")

    event = db.query(Event).filter(
        Event.id == data.event_id,
        Event.firebase_uid == user.firebase_uid
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status not in ["COMPLETED", "SURPLUS_AVAILABLE"]:
        raise HTTPException(status_code=400, detail="Event not completed")

    event_location = (
        db.query(EventLocation)
        .filter(EventLocation.event_id == event.id)
        .first()
    )

    # Use the event's saved location as the source of truth.
    alert_latitude = event_location.latitude if event_location else data.latitude
    alert_longitude = event_location.longitude if event_location else data.longitude

    # ---------------- SAVE SURPLUS REQUEST ----------------

    surplus = SurplusRequest(
        event_id=event.id,
        organizer_id=db_user.id,
        food_description=data.food_description,
        image_url=data.image_url,
        latitude=alert_latitude,
        longitude=alert_longitude
    )

    db.add(surplus)
    db.flush()

    event.surplus_request_id = surplus.id
    db.commit()
    db.refresh(surplus)

    # ---------------- DISTANCE CALCULATION ----------------

    distance_expr = (
        6371 * func.acos(
            func.cos(func.radians(alert_latitude)) *
            func.cos(func.radians(NGOProfile.latitude)) *
            func.cos(func.radians(NGOProfile.longitude) - func.radians(alert_longitude)) +
            func.sin(func.radians(alert_latitude)) *
            func.sin(func.radians(NGOProfile.latitude))
        )
    )

    ngos = (
        db.query(NGO, distance_expr.label("distance"))
        .join(User, User.firebase_uid == NGO.firebase_uid)
        .join(NGOProfile, NGOProfile.user_id == User.id)
        .filter(NGOProfile.latitude.isnot(None), NGOProfile.longitude.isnot(None))
        .filter(distance_expr < 30)
        .all()
    )

    # ---------------- SEND ALERTS ----------------

    # Build a contact lookup so every connected NGO receives a payload.
    ngo_contact_map = {}
    for ngo, distance in ngos:
        ngo_name, phone = _get_ngo_contact_info(db, ngo)
        ngo_contact_map[ngo.id] = {
            "distance": round(distance, 2),
            "ngo_name": ngo_name,
            "phone": phone,
        }

    base_payload = {
        "type": "surplus_food",
        "request_id": surplus.id,
        "event_name": event.event_name,
        "food_description": data.food_description,
        "image_url": data.image_url,
        "latitude": alert_latitude,
        "longitude": alert_longitude,
    }

    print("SENDING ALERT TO NGOs:", base_payload)

    for ngo_id, ws in manager.ngo_connections.items():
        ngo_details = ngo_contact_map.get(
            ngo_id,
            {"distance": None, "ngo_name": "", "phone": ""}
        )
        payload = {
            **base_payload,
            "distance": ngo_details["distance"],
            "ngo_name": ngo_details["ngo_name"],
            "phone": ngo_details["phone"],
        }
        await ws.send_json(payload)

    return {
        "request_id": surplus.id,
        "message": "Surplus alert sent successfully"
    }


@router.get("/{request_id:int}")
def get_surplus_request(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    request = db.query(SurplusRequest).filter(
        SurplusRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    return {
        "request_id": request.id,
        "latitude": request.latitude,
        "longitude": request.longitude
    }


@router.get("/{request_id:int}/route")
def get_route(request_id: int, db: Session = Depends(get_db)):
    request_obj = db.query(SurplusRequest).filter(
        SurplusRequest.id == request_id
    ).first()

    if not request_obj:
        raise HTTPException(status_code=404, detail="Request not found")

    # Example organizer location for route origin.
    origin_lat = 28.6139
    origin_lng = 77.2090

    dest_lat = request_obj.latitude
    dest_lng = request_obj.longitude

    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=false"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"OSRM request failed: {str(exc)}") from exc

    routes = payload.get("routes") or []
    if not routes:
        raise HTTPException(status_code=404, detail="No route found")

    route = routes[0]

    return {
        "distance_km": route["distance"] / 1000,
        "duration_min": route["duration"] / 60
    }

@router.get("/{request_id:int}/nearby-ngos", response_model=list[SurplusNgoResponse])
def get_nearby_ngos(
    request_id: int,
    db: Session = Depends(get_db)
):

    request = db.query(SurplusRequest).filter(
        SurplusRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    distance_expr = (
        6371 * func.acos(
            func.cos(func.radians(request.latitude)) *
            func.cos(func.radians(NGOProfile.latitude)) *
            func.cos(func.radians(NGOProfile.longitude) - func.radians(request.longitude)) +
            func.sin(func.radians(request.latitude)) *
            func.sin(func.radians(NGOProfile.latitude))
        )
    )

    ngos = (
        db.query(NGO, distance_expr.label("distance"))
        .join(User, User.firebase_uid == NGO.firebase_uid)
        .join(NGOProfile, NGOProfile.user_id == User.id)
        .filter(NGOProfile.latitude.isnot(None), NGOProfile.longitude.isnot(None))
        .filter(distance_expr < 30)
        .all()
    )

    return [
        {
            "id": ngo.id,
            "ngo_name": _get_ngo_contact_info(db, ngo)[0],
            "phone": _get_ngo_contact_info(db, ngo)[1],
        }
        for ngo, _distance in ngos
    ]

@router.post("/{request_id:int}/accept")
async def accept_surplus(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "ngo":
        raise HTTPException(status_code=403, detail="Only NGOs allowed")

    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user.firebase_uid
    ).first()

    if not ngo:
        raise HTTPException(status_code=404, detail="NGO profile not found")

    request = db.query(SurplusRequest).filter(
        SurplusRequest.id == request_id
    ).with_for_update().first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "OPEN":
        raise HTTPException(status_code=400, detail="Already accepted")

    request.status = "ACCEPTED"
    request.accepted_by_ngo = ngo.id

    db.commit()

    # ✅ GET NGO INFO FOR NOTIFICATION
    ngo_name, phone = _get_ngo_contact_info(db, ngo)

    # ✅ SEND PUSH NOTIFICATION TO ORGANIZER
    try:
        organizer_user = db.query(User).filter(
            User.id == request.organizer_id
        ).first()
        if organizer_user and organizer_user.fcm_token:
            send_push_notification(
                organizer_user.fcm_token,
                "NGO Accepted",
                f"{ngo_name} has accepted your food donation",
                data={"request_id": str(request.id), "ngo_id": str(ngo.id)}
            )
    except Exception as exc:
        logger.warning(
            f"Failed to send push notification for accept_surplus request_id={request_id}: {str(exc)}"
        )

    await manager.notify_organizer(
        request.organizer_id,
        {
            "type": "ngo_accepted",
            "ngo_name": ngo_name,
            "phone": phone,
            "request_id": request.id,
        }
    )

    return {"message": "Surplus accepted"}

@router.get("/{request_id:int}/accepted-ngo", response_model=SurplusNgoResponse)
def get_accepted_ngo(
    request_id: int,
    db: Session = Depends(get_db)
):

    request = db.query(SurplusRequest).filter(
        SurplusRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if not request.accepted_by_ngo:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    ngo = db.query(NGO).filter(
        NGO.id == request.accepted_by_ngo
    ).first()

    if not ngo:
        raise HTTPException(status_code=404, detail="Accepted NGO not found")

    ngo_name, phone = _get_ngo_contact_info(db, ngo)

    return {
        "id": ngo.id,
        "ngo_name": ngo_name,
        "phone": phone
    }

@router.post("/{request_id:int}/reject")
async def reject_surplus(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "ngo":
        raise HTTPException(status_code=403, detail="Only NGOs allowed")

    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user.firebase_uid
    ).first()

    request = db.query(SurplusRequest).filter(
        SurplusRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "OPEN":
        raise HTTPException(status_code=400, detail="Already processed")

    request.status = "REJECTED"

    db.commit()

    return {"message": "Surplus rejected"}


@router.get("/my-accepted", response_model=list[SurplusAcceptedResponse])
def get_my_accepted_requests(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "ngo":
        raise HTTPException(status_code=403, detail="Only NGOs allowed")

    ngo = db.query(NGO).filter(
        NGO.firebase_uid == user.firebase_uid
    ).first()

    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    # ✅ CORRECT QUERY
    requests = (
        db.query(SurplusRequest, Event, Organizer)
        .join(Event, Event.id == SurplusRequest.event_id)
        .join(Organizer, Organizer.user_id == SurplusRequest.organizer_id)
        .filter(
            SurplusRequest.accepted_by_ngo == ngo.id,
            SurplusRequest.status == "ACCEPTED"
        )
        .order_by(SurplusRequest.created_at.desc())
        .all()
    )

    result = []

    for req, event, organizer in requests:
        result.append({
            "request_id": req.id,
            "event_id": req.event_id,
            "organizer_id": req.organizer_id,
            "event_name": event.event_name,
            "food_description": req.food_description,
            "image_url": req.image_url,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "status": req.status,
            "accepted_by_ngo": req.accepted_by_ngo,
            "created_at": req.created_at,

            # ✅ CORRECT SOURCE
            "organizer_name": organizer.full_name,
            "organizer_phone": organizer.phone
        })

    return result