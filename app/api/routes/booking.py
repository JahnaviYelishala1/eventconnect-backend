from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.booking_item import BookingItem
from app.models.caterer_menu import CatererMenu
from app.models.event_booking import EventBooking
from app.models.caterer import Caterer
from app.models.event import Event
from app.models.user import User
from app.schemas.booking import BookingResponse
from app.utils.auth import get_current_user
from app.schemas.booking import BookingCreate
router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


# ---------------- HOST REQUEST BOOKING ----------------
@router.post("/request", response_model=BookingResponse)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "organizer":
        raise HTTPException(403, "Only organizers allowed")

    event = db.query(Event).filter(
        Event.id == data.event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    caterer = db.query(Caterer).filter(
        Caterer.id == data.caterer_id
    ).first()

    if not caterer:
        raise HTTPException(404, "Caterer not found")

    total_price = 0

    booking = EventBooking(
        event_id=event.id,
        caterer_id=caterer.id,
        status="pending",
        total_price=0
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    for item in data.items:

        menu = db.query(CatererMenu).filter(
            CatererMenu.id == item.menu_id,
            CatererMenu.caterer_id == caterer.id
        ).first()

        if not menu:
            raise HTTPException(404, "Menu item invalid")

        total_price += menu.price * item.quantity

        db.add(BookingItem(
            booking_id=booking.id,
            menu_id=menu.id,
            quantity=item.quantity
        ))

    booking.total_price = total_price
    db.commit()

    return booking

@router.get("/caterer", response_model=List[BookingResponse])
def get_caterer_bookings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    return db.query(EventBooking).filter(
        EventBooking.caterer_id == caterer.id
    ).all()

@router.put("/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    if status not in ["accepted", "rejected"]:
        raise HTTPException(400, "Invalid status")

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    booking.status = status
    db.commit()

    return {"message": f"Booking {status}"}