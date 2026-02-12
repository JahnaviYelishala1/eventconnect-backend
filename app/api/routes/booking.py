from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.event_booking import EventBooking
from app.models.caterer import Caterer
from app.models.event import Event
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


# ---------------- HOST REQUEST BOOKING ----------------
@router.post("/request/{event_id}/{caterer_id}")
def request_booking(
    event_id: int,
    caterer_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    booking = EventBooking(
        event_id=event_id,
        caterer_id=caterer_id
    )

    event.status = "BOOKING_REQUESTED"

    db.add(booking)
    db.commit()

    return {"message": "Booking requested"}


# ---------------- CATERER VIEW REQUESTS ----------------
@router.get("/caterer-requests")
def get_caterer_requests(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    caterer_user = db.query(User).filter(
        User.firebase_uid == user["uid"],
        User.role == "caterer"
    ).first()

    if not caterer_user:
        raise HTTPException(403, "Not authorized")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == caterer_user.id
    ).first()

    if not caterer:
        return []

    bookings = (
        db.query(EventBooking)
        .join(Event, EventBooking.event_id == Event.id)
        .filter(
            EventBooking.caterer_id == caterer.id,
            EventBooking.status == "PENDING"
        )
        .all()
    )

    result = []

    for booking in bookings:
        event = booking.event

        result.append({
            "booking_id": booking.id,
            "event_id": event.id,
            "event_name": event.event_name,
            "event_type": event.event_type,
            "attendees": event.attendees,
            "duration_hours": event.duration_hours,
            "meal_style": event.meal_style,
            "location_type": event.location_type,
            "estimated_food_quantity": event.estimated_food_quantity,
            "unit": event.unit,
            "status": booking.status
        })

    return result


    result = []

    for booking in bookings:
        event = booking.event

        result.append({
            "booking_id": booking.id,
            "event_id": event.id,
            "event_name": event.event_name,
            "event_type": event.event_type,
            "attendees": event.attendees,
            "duration_hours": event.duration_hours,
            "meal_style": event.meal_style,
            "location_type": event.location_type,
            "estimated_food_quantity": event.estimated_food_quantity,
            "unit": event.unit,
            "status": booking.status
        })

    return result


# ---------------- ACCEPT / REJECT ----------------
@router.patch("/respond/{booking_id}")
def respond_booking(
    booking_id: int,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    if status not in ["ACCEPTED", "REJECTED"]:
        raise HTTPException(400, "Invalid status")

    booking.status = status

    event = db.query(Event).filter(
        Event.id == booking.event_id
    ).first()

    if status == "ACCEPTED":
        event.status = "BOOKED"
    else:
        event.status = "CREATED"

    db.commit()

    return {"message": f"Booking {status}"}

@router.get("/event/{event_id}")
def get_event_booking_status(
    event_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    booking = db.query(EventBooking).filter(
        EventBooking.event_id == event_id
    ).first()

    if not booking:
        return {
            "event_id": event_id,
            "status": "NONE",
            "caterer_name": None
        }

    caterer = db.query(Caterer).filter(
        Caterer.id == booking.caterer_id
    ).first()

    return {
        "event_id": event_id,
        "status": booking.status,
        "caterer_name": caterer.business_name if caterer else None
    }
