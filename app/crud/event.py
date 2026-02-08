from sqlalchemy.orm import Session
from app.models.event import Event
from app.schemas.event import EventCreate

def create_event(
    db: Session,
    firebase_uid: str,
    data: EventCreate,
    estimated_food_quantity: float
):
    event = Event(
        firebase_uid=firebase_uid,
        event_name=data.event_name,
        event_type=data.event_type,
        attendees=data.attendees,
        duration_hours=data.duration_hours,
        meal_style=data.meal_style,
        location_type=data.location_type,
        season=data.season,
        estimated_food_quantity=estimated_food_quantity,
        unit="kg"
    )

    db.add(event)
    db.commit()
    db.refresh(event)
    return event
