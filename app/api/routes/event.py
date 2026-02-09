from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.event import EventCreate, EventResponse, EventComplete
from app.ml.predictor import predict_food_quantity
from app.crud.event import create_event
from app.utils.auth import get_current_user
from app.models.event import Event
from app.models.event_location import EventLocation

router = APIRouter(
    prefix="/api/events",
    tags=["Events"]
)


@router.post("", response_model=EventResponse)
def create_event_api(
    data: EventCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    features = [
        data.event_type,
        data.attendees,
        data.duration_hours,
        data.meal_style,
        data.location_type,
        data.season
    ]

    predicted_food = predict_food_quantity(features)

    event = create_event(
        db=db,
        firebase_uid=user["uid"],
        data=data,
        estimated_food_quantity=predicted_food
    )

    return event


@router.get("/my-events")
def get_my_events(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return (
        db.query(Event)
        .filter(Event.firebase_uid == user["uid"])
        .order_by(Event.id.desc())
        .all()
    )


@router.patch("/{event_id}/complete")
def complete_event(
    event_id: int,
    data: EventComplete,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.firebase_uid == user["uid"]
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    surplus = data.food_prepared - data.food_consumed

    # ---------------- VALIDATION ----------------
    if surplus > 0:
        if not data.surplus_location:
            raise HTTPException(
                status_code=400,
                detail="Surplus detected. Pickup location required."
            )

        if (
            data.surplus_location.latitude is None or
            data.surplus_location.longitude is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Latitude and longitude are required for surplus pickup"
            )

        existing_location = (
            db.query(EventLocation)
            .filter(EventLocation.event_id == event.id)
            .first()
        )

        if existing_location:
            raise HTTPException(
                status_code=409,
                detail="Pickup location already exists for this event"
            )
    # --------------------------------------------

    event.food_prepared = data.food_prepared
    event.food_consumed = data.food_consumed
    event.food_surplus = max(surplus, 0)

    if surplus > 0:
        location = EventLocation(
            event_id=event.id,
            address=data.surplus_location.address,
            city=data.surplus_location.city,
            pincode=data.surplus_location.pincode,
            latitude=data.surplus_location.latitude,
            longitude=data.surplus_location.longitude,
            location_type=data.surplus_location.location_type
        )

        db.add(location)
        event.status = "SURPLUS_AVAILABLE"
    else:
        event.status = "COMPLETED"

    db.commit()
    db.refresh(event)

    return {
        "event_id": event.id,
        "surplus": event.food_surplus,
        "status": event.status
    }
