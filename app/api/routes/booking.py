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

    if not db_user or db_user.role != "event_organizer":
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

    try:

        total_price = 0

        booking = EventBooking(
            event_id=event.id,
            caterer_id=caterer.id,
            organizer_id=db_user.id, 
            attendees=data.attendees,
            booking_date=data.booking_date,
            status="pending"
        )

        db.add(booking)
        db.flush()  # Get booking.id without full commit

        for item in data.items:

            menu = db.query(CatererMenu).filter(
                CatererMenu.id == item.menu_id,
                CatererMenu.caterer_id == caterer.id
            ).first()

            if not menu:
                raise HTTPException(404, "Invalid menu item")

            total_price += menu.price * item.quantity

            db.add(BookingItem(
                booking_id=booking.id,
                menu_id=menu.id,
                quantity=item.quantity
            ))

        booking.total_price = total_price

        db.commit()
        db.refresh(booking)

        return booking

    except Exception as e:
        db.rollback()
        raise HTTPException(400, str(e))

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

    if not caterer:
        raise HTTPException(404, "Caterer not found")

    bookings = db.query(EventBooking).filter(
        EventBooking.caterer_id == caterer.id
    ).order_by(EventBooking.created_at.desc()).all()

    result = []

    for booking in bookings:

        event = db.query(Event).filter(
            Event.id == booking.event_id
        ).first()

        items_query = (
            db.query(BookingItem, CatererMenu)
            .join(CatererMenu, CatererMenu.id == BookingItem.menu_id)
            .filter(BookingItem.booking_id == booking.id)
            .all()
        )

        items_list = []

        for booking_item, menu in items_query:
            items_list.append({
                "menu_id": menu.id,
                "item_name": menu.item_name,
                "quantity": booking_item.quantity,
                "price": menu.price
            })

        result.append({
            "id": booking.id,
            "event_id": booking.event_id,
            "caterer_id": booking.caterer_id,
            "attendees": booking.attendees,
            "booking_date": booking.booking_date,
            "status": booking.status,
            "total_price": booking.total_price,
            "caterer_name": None,
            "event_name": event.event_name if event else None,
            "items": items_list
        })

    return result

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

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id,
        EventBooking.caterer_id == caterer.id
    ).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    if booking.status != "pending":
        raise HTTPException(400, "Booking already finalized")

    booking.status = status
    db.commit()

    return {"message": f"Booking {status}"}

@router.get("/organizer", response_model=List[BookingResponse])
def get_organizer_bookings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(403, "Only organizers allowed")

    bookings = db.query(EventBooking).filter(
        EventBooking.organizer_id == db_user.id
    ).order_by(EventBooking.created_at.desc()).all()

    result = []

    for booking in bookings:

        caterer = db.query(Caterer).filter(
            Caterer.id == booking.caterer_id
        ).first()

        items_query = (
            db.query(BookingItem, CatererMenu)
            .join(CatererMenu, CatererMenu.id == BookingItem.menu_id)
            .filter(BookingItem.booking_id == booking.id)
            .all()
        )

        items_list = []

        for booking_item, menu in items_query:
            items_list.append({
                "menu_id": menu.id,
                "item_name": menu.item_name,
                "quantity": booking_item.quantity,
                "price": menu.price
            })

        result.append({
            "id": booking.id,
            "event_id": booking.event_id,
            "caterer_id": booking.caterer_id,
            "attendees": booking.attendees,
            "booking_date": booking.booking_date,
            "status": booking.status,
            "total_price": booking.total_price,
            "caterer_name": caterer.business_name if caterer else None,
            "event_name": None,
            "items": items_list
        })

    return result