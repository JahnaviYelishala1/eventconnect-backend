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
from collections import defaultdict



router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


def _build_booking_response(
    booking,
    caterer_name,
    event_name,
    items_list,
):
    return {
        "id": booking.id,
        "event_id": booking.event_id,
        "caterer_id": booking.caterer_id,
        "attendees": booking.attendees,
        "booking_date": booking.booking_date,
        "created_at": booking.created_at,
        "status": booking.status,
        "total_price": booking.total_price,
        "caterer_name": caterer_name,
        "event_name": event_name,
        "items": items_list,
    }


# ==========================================================
# HOST REQUEST BOOKING
# ==========================================================
@router.post("/request", response_model=BookingResponse)
async def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(status_code=403, detail="Only organizers allowed")

    event = db.query(Event).filter(
        Event.id == data.event_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if hasattr(event, "organizer_id") and getattr(event, "organizer_id") is not None:
        if event.organizer_id != db_user.id:
            raise HTTPException(status_code=403, detail="Not your event")
    elif event.firebase_uid != db_user.firebase_uid:
        raise HTTPException(status_code=403, detail="Not your event")

    caterer = db.query(Caterer).filter(
        Caterer.id == data.caterer_id
    ).first()

    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")

    try:
        print("BOOKING REQUEST:")
        print("User:", db_user.id)
        print("Event ID:", data.event_id)
        print("Caterer ID:", data.caterer_id)
        print("Items:", data.items)
        print("VALIDATING MENU ITEMS...")
        print("CATERER:", caterer.id)
        print("ITEMS:", data.items)

        invalid_items = []
        menu_lookup = {}

        for item in data.items:
            menu = db.query(CatererMenu).filter(
                CatererMenu.id == item.menu_id
            ).first()

            if not menu:
                invalid_items.append(f"{item.menu_id} (not found)")
                continue

            if menu.caterer_id != caterer.id:
                invalid_items.append(f"{item.menu_id} (wrong caterer)")
                continue

            menu_lookup[item.menu_id] = menu

        if invalid_items:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid menu items: {invalid_items}"
            )

        total_price = 0

        booking_date = data.booking_date
        if isinstance(booking_date, str):
            booking_date = datetime.strptime(booking_date, "%Y-%m-%d")

        booking = EventBooking(
            event_id=event.id,
            caterer_id=caterer.id,
            organizer_id=db_user.id,
            attendees=data.attendees,
            booking_date=booking_date,
            created_at=datetime.utcnow(),
            status="pending"
        )

        db.add(booking)
        db.flush()

        for item in data.items:
            menu = menu_lookup[item.menu_id]

            total_price += menu.price * item.quantity

            db.add(BookingItem(
                booking_id=booking.id,
                menu_id=menu.id,
                quantity=item.quantity
            ))

        booking.total_price = total_price
        db.commit()
        db.refresh(booking)
        print("BOOKING CREATED:", booking.id)
        print("TOTAL PRICE:", total_price)

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

        # Notify caterer instantly (non-blocking for booking success)
        try:
            await manager.send_personal_message(
                str(caterer.user_id),
                {
                    "type": "new_booking",
                    "booking_id": booking.id,
                    "status": booking.status
                }
            )
        except Exception as e:
            print("WebSocket notification failed:", e)

        return {
            "id": booking.id,
            "event_id": booking.event_id,
            "caterer_id": booking.caterer_id,
            "attendees": booking.attendees,
            "booking_date": booking.booking_date,
            "created_at": booking.created_at,
            "status": booking.status,
            "total_price": booking.total_price,
            "caterer_name": caterer.business_name,
            "event_name": event.event_name,
            "items": items_list
        }

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# GET CATERER BOOKINGS
# ==========================================================
@router.get("/caterer", response_model=List[BookingResponse])
def get_caterer_bookings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "caterer":
        return []

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        return []

    bookings = db.query(EventBooking).filter(
        EventBooking.caterer_id == caterer.id
    ).order_by(EventBooking.created_at.desc()).all()

    if not bookings:
        return []

    booking_ids = [booking.id for booking in bookings]
    event_ids = list({booking.event_id for booking in bookings})

    events = {
        event.id: event
        for event in db.query(Event).filter(Event.id.in_(event_ids)).all()
    }

    booking_items = (
        db.query(BookingItem, CatererMenu)
        .join(CatererMenu, CatererMenu.id == BookingItem.menu_id)
        .filter(BookingItem.booking_id.in_(booking_ids))
        .all()
    )

    items_by_booking = defaultdict(list)

    for booking_item, menu in booking_items:
        items_by_booking[booking_item.booking_id].append({
            "menu_id": menu.id,
            "item_name": menu.item_name,
            "quantity": booking_item.quantity,
            "price": menu.price,
        })

    result = []

    for booking in bookings:
        event = events.get(booking.event_id)

        result.append(_build_booking_response(
            booking,
            caterer.business_name,
            event.event_name if event else None,
            items_by_booking.get(booking.id, []),
        ))

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

    db_user = user

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

    # If accepted, create a pending payment record.
    if status == "accepted":
        payment = Payment(
            booking_id=booking.id,
            amount=booking.total_price,
            status="pending",
            stripe_payment_intent=f"pending_{booking.id}_{int(datetime.utcnow().timestamp())}",
            currency="inr"
        )
        db.add(payment)
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


@router.post("/payments/create-session/{booking_id}")
def create_payment_session(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    if booking.status != "accepted":
        raise HTTPException(400, "Booking not ready for payment")

    # Dummy checkout URL; can be replaced by Stripe checkout later.
    checkout_url = f"https://dummy-payment.com/pay/{booking_id}"

    return {
        "checkout_url": checkout_url
    }


@router.post("/payments/success/{booking_id}")
async def payment_success(
    booking_id: int,
    db: Session = Depends(get_db)
):
    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(404, "Booking not found")

    booking.status = "paid"

    payment = db.query(Payment).filter(
        Payment.booking_id == booking_id
    ).first()

    if payment:
        payment.status = "paid"

    db.commit()

    # Optional: notify caterer on payment received.
    try:
        await manager.send_personal_message(
            str(booking.caterer.user_id),
            {
                "type": "payment_received",
                "booking_id": booking.id
            }
        )
    except Exception:
        pass

    return {"message": "Payment successful"}


# ==========================================================
# GET ORGANIZER BOOKINGS
# ==========================================================
@router.get("/organizer", response_model=List[BookingResponse])
def get_organizer_bookings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = user

    if not db_user or db_user.role != "event_organizer":
        raise HTTPException(status_code=403, detail="Only organizers allowed")

    bookings = db.query(EventBooking).filter(
        EventBooking.organizer_id == db_user.id
    ).order_by(EventBooking.created_at.desc()).all()

    if not bookings:
        return []

    booking_ids = [booking.id for booking in bookings]
    caterer_ids = list({booking.caterer_id for booking in bookings})
    event_ids = list({booking.event_id for booking in bookings})

    caterers = {
        caterer.id: caterer
        for caterer in db.query(Caterer).filter(Caterer.id.in_(caterer_ids)).all()
    }

    events = {
        event.id: event
        for event in db.query(Event).filter(Event.id.in_(event_ids)).all()
    }

    booking_items = (
        db.query(BookingItem, CatererMenu)
        .join(CatererMenu, CatererMenu.id == BookingItem.menu_id)
        .filter(BookingItem.booking_id.in_(booking_ids))
        .all()
    )

    items_by_booking = defaultdict(list)

    for booking_item, menu in booking_items:
        items_by_booking[booking_item.booking_id].append({
            "menu_id": menu.id,
            "item_name": menu.item_name,
            "quantity": booking_item.quantity,
            "price": menu.price,
        })

    result = []

    for booking in bookings:
        caterer = caterers.get(booking.caterer_id)
        event = events.get(booking.event_id)

        result.append(_build_booking_response(
            booking,
            caterer.business_name if caterer else None,
            event.event_name if event else None,
            items_by_booking.get(booking.id, []),
        ))

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
    db_user = user

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
    db_user = user

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
        "created_at": booking.created_at,
        "status": booking.status,
        "total_price": booking.total_price,
        "caterer_name": caterer.business_name if caterer else None,
        "event_name": event.event_name if event else None,
        "items": items_list
    }