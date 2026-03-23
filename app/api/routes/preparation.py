from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.event_booking import EventBooking
from app.models.caterer import Caterer
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/bookings", tags=["Preparation"])

PREPARATION_STAGES = [
    "pending",
    "ingredients_ready",
    "cooking_started",
    "packing",
    "out_for_delivery",
    "arrived"
]


class PreparationStatusUpdate(BaseModel):
    status: str


@router.put("/{booking_id}/preparation-status")
def update_preparation_status(
    booking_id: int,
    payload: Optional[PreparationStatusUpdate] = Body(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    print("USER UID:", user["uid"])

    new_status = payload.status if payload else status
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")

    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if new_status not in PREPARATION_STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")

    db_user = db.query(User).filter(
        User.firebase_uid == user["uid"]
    ).first()

    if not db_user:
        raise HTTPException(status_code=403, detail="Forbidden")

    print("DB USER ID:", db_user.id)

    caterer = db.query(Caterer).filter(
        Caterer.user_id == db_user.id
    ).first()

    if not caterer:
        raise HTTPException(status_code=403, detail="Forbidden")

    if caterer.id != booking.caterer_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    booking.preparation_status = new_status
    db.commit()

    return {"message": "Preparation status updated", "status": new_status}


@router.get("/{booking_id}/preparation-status")
def get_preparation_status(
    booking_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    booking = db.query(EventBooking).filter(
        EventBooking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    return {
        "status": booking.preparation_status
    }
