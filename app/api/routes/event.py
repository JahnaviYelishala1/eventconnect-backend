from multiprocessing import Event
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.event import EventCreate, EventResponse
from app.ml.predictor import predict_food_quantity
from app.crud.event import create_event
from app.utils.auth import get_current_user
from app.models.event import Event

router = APIRouter(
    prefix="/api/events",
    tags=["Events"]
)

@router.post("", response_model=EventResponse)
def create_event_api(
    data: EventCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Prepare ML features
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
    user = Depends(get_current_user)
):
    return (
        db.query(Event)
        .filter(Event.firebase_uid == user["uid"])
        .order_by(Event.id.desc())
        .all()
    )