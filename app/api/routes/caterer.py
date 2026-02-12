from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.caterer import Caterer
from app.models.caterer_service import CatererService
from app.models.event import Event
from app.models.event_booking import EventBooking
from app.schemas.caterer import CatererCreate
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/caterers", tags=["Caterers"])

@router.post("/profile")
def create_caterer_profile(
    data: CatererCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if db_user.role != "caterer":
        raise HTTPException(403, "Only caterers allowed")

    existing = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if existing:
        raise HTTPException(400, "Profile already exists")

    caterer = Caterer(
        user_id=db_user.id,
        business_name=data.business_name,
        city=data.city,
        min_capacity=data.min_capacity,
        max_capacity=data.max_capacity,
        price_per_plate=data.price_per_plate,
        veg_supported=data.veg_supported,
        nonveg_supported=data.nonveg_supported
    )

    db.add(caterer)
    db.commit()
    db.refresh(caterer)

    for service in data.services:
        db.add(CatererService(
            caterer_id=caterer.id,
            service_type=service
        ))

    db.commit()

    return {"message": "Caterer profile created"}

@router.get("/match/{event_id}")
def match_caterers(
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

    caterers = db.query(Caterer).filter(
        Caterer.city == event.location_type,
        Caterer.min_capacity <= event.attendees,
        Caterer.max_capacity >= event.attendees
    ).all()

    return caterers

@router.post("/book/{event_id}/{caterer_id}")
def book_caterer(
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
        caterer_id=caterer_id,
        status="PENDING"
    )

    event.status = "BOOKING_REQUESTED"

    db.add(booking)
    db.commit()

    return {"message": "Booking request sent"}

