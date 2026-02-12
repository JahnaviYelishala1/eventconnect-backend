from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.booking import Booking
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

    booking = Booking(
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

    caterer = db.query(User).filter(
        User.firebase_uid == user["uid"],
        User.role == "caterer"
    ).first()

    if not caterer:
        raise HTTPException(403, "Not authorized")

    bookings = (
        db.query(Booking)
        .join(Event, Booking.event_id == Event.id)
        .filter(
            Booking.caterer_id == caterer.id,
            Booking.status == "PENDING"
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


# ---------------- ACCEPT / REJECT ----------------
@router.patch("/respond/{booking_id}")
def respond_booking(
    booking_id: int,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    booking = db.query(Booking).filter(
        Booking.id == booking_id
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

