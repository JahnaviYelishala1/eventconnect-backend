from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from calendar import month_abbr
from sqlalchemy import func

from app.database import get_db
from app.models.booking_item import BookingItem
from app.models.caterer_menu import CatererMenu
from app.models.event_booking import EventBooking
from app.models.caterer import Caterer
from app.models.event import Event
from app.models.user import User
from app.schemas.booking import BookingResponse, BookingCreate
from app.utils.auth import get_current_user
from app.websocket.manager import manager
from sqlalchemy import func
from datetime import datetime
from app.models.payment import Payment



router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


# ==========================================================
# HOST REQUEST BOOKING
# ==========================================================
@router.post("/request", response_model=BookingResponse)
async def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(status_code=403, detail="Only organizers allowed")

    event = db.query(Event).filter(
        Event.id == data.event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    caterer = db.query(Caterer).filter(
        Caterer.id == data.caterer_id
    ).first()

    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")

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
        db.flush()

        for item in data.items:
            menu = db.query(CatererMenu).filter(
                CatererMenu.id == item.menu_id,
                CatererMenu.caterer_id == caterer.id
            ).first()

            if not menu:
                raise HTTPException(status_code=404, detail="Invalid menu item")

            total_price += menu.price * item.quantity

            db.add(BookingItem(
                booking_id=booking.id,
                menu_id=menu.id,
                quantity=item.quantity
            ))

        booking.total_price = total_price
        db.commit()
        db.refresh(booking)

        # Build response manually to match BookingResponse
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

        # Notify caterer instantly
        await manager.send_personal_message(
            str(caterer.user_id),
            {
                "type": "new_booking",
                "booking_id": booking.id,
                "status": booking.status
            }
        )

        return {
            "id": booking.id,
            "event_id": booking.event_id,
            "caterer_id": booking.caterer_id,
            "attendees": booking.attendees,
            "booking_date": booking.booking_date,
            "status": booking.status,
            "total_price": booking.total_price,
            "caterer_name": caterer.business_name,
            "event_name": event.event_name,
            "items": items_list
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================================
# GET CATERER BOOKINGS
# ==========================================================
@router.get("/caterer", response_model=List[BookingResponse])
def get_caterer_bookings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(status_code=403, detail="Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")

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
            "caterer_name": caterer.business_name,
            "event_name": event.event_name if event else None,
            "items": items_list
        })

    return result


# ==========================================================
# UPDATE BOOKING STATUS (CATERER)
# ==========================================================
@router.put("/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if status not in ["accepted", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(status_code=403, detail="Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id,
        EventBooking.caterer_id == caterer.id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="Booking already finalized")

    booking.status = status
    db.commit()

    await manager.send_personal_message(
        str(booking.organizer_id),
        {
            "type": "booking_updated",
            "booking_id": booking.id,
            "status": booking.status
        }
    )

    return {"message": f"Booking {status}"}


# ==========================================================
# GET ORGANIZER BOOKINGS
# ==========================================================
@router.get("/organizer", response_model=List[BookingResponse])
def get_organizer_bookings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(status_code=403, detail="Only organizers allowed")

    bookings = db.query(EventBooking).filter(
        EventBooking.organizer_id == db_user.id
    ).order_by(EventBooking.created_at.desc()).all()

    result = []

    for booking in bookings:

        caterer = db.query(Caterer).filter(
            Caterer.id == booking.caterer_id
        ).first()

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
            "caterer_name": caterer.business_name if caterer else None,
            "event_name": event.event_name if event else None,
            "items": items_list
        })

    return result


# ==========================================================
# CANCEL BOOKING (ORGANIZER)
# ==========================================================
@router.put("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(status_code=403, detail="Only organizers allowed")

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id,
        EventBooking.organizer_id == db_user.id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status not in ["pending", "accepted"]:
        raise HTTPException(status_code=400, detail="Cannot cancel this booking")

    booking.status = "cancelled"
    db.commit()

    await manager.send_personal_message(
        str(booking.caterer.user_id),
        {
            "type": "booking_cancelled",
            "booking_id": booking.id,
            "status": booking.status
        }
    )

    return {"message": "Booking cancelled"}

@router.get("/caterer/revenue")
def get_caterer_revenue(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user or db_user.role != "caterer":
        raise HTTPException(status_code=403, detail="Only caterers allowed")

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")

    # ------------------------------------------------------
    # Get all bookings for this caterer
    # ------------------------------------------------------
    bookings = db.query(EventBooking).filter(
        EventBooking.caterer_id == caterer.id
    ).all()

    booking_ids = [b.id for b in bookings]

    if not booking_ids:
        return {
            "total_revenue": 0,
            "total_paid_bookings": 0,
            "pending_bookings": 0,
            "this_month_revenue": 0,
            "monthly_breakdown": []
        }

    # ------------------------------------------------------
    # Total revenue
    # ------------------------------------------------------
    total_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.booking_id.in_(booking_ids),
        Payment.status == "paid"
    ).scalar()

    # ------------------------------------------------------
    # Total paid bookings
    # ------------------------------------------------------
    total_paid = db.query(func.count(Payment.id)).filter(
        Payment.booking_id.in_(booking_ids),
        Payment.status == "paid"
    ).scalar()

    # ------------------------------------------------------
    # Pending bookings
    # ------------------------------------------------------
    pending_count = db.query(func.count(EventBooking.id)).filter(
        EventBooking.caterer_id == caterer.id,
        EventBooking.status.in_(["pending", "accepted"])
    ).scalar()

    # ------------------------------------------------------
    # This month revenue
    # ------------------------------------------------------
    now = datetime.utcnow()
    first_day = datetime(now.year, now.month, 1)

    this_month_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.booking_id.in_(booking_ids),
        Payment.status == "paid",
        Payment.paid_at >= first_day
    ).scalar()

    # ------------------------------------------------------
    # Monthly breakdown
    # ------------------------------------------------------
    monthly_data = db.query(
        func.date_trunc("month", Payment.paid_at).label("month"),
        func.sum(Payment.amount)
    ).filter(
        Payment.booking_id.in_(booking_ids),
        Payment.status == "paid"
    ).group_by("month").order_by("month").all()

    monthly_breakdown = [
        {
            "month": m.month.strftime("%Y-%m"),
            "revenue": float(m[1])
        }
        for m in monthly_data
    ]

    return {
        "total_revenue": float(total_revenue),
        "total_paid_bookings": total_paid,
        "pending_bookings": pending_count,
        "this_month_revenue": float(this_month_revenue),
        "monthly_breakdown": monthly_breakdown
    }

# ==========================================================
# GET BOOKING DETAILS
# ==========================================================
@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_details(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    caterer = db.query(Caterer).filter(
        Caterer.id == booking.caterer_id
    ).first()

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

    return {
        "id": booking.id,
        "event_id": booking.event_id,
        "caterer_id": booking.caterer_id,
        "attendees": booking.attendees,
        "booking_date": booking.booking_date,
        "status": booking.status,
        "total_price": booking.total_price,
        "caterer_name": caterer.business_name if caterer else None,
        "event_name": event.event_name if event else None,
        "items": items_list
    }