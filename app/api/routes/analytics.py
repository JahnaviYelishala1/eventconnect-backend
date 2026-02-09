from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.event import Event

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"]
)

@router.get("/food-training-data")
def get_food_training_data(db: Session = Depends(get_db)):
    events = (
        db.query(Event)
        .filter(Event.status.in_(["COMPLETED", "SURPLUS_AVAILABLE"]))
        .all()
    )

    return [
        {
            "event_type": e.event_type,
            "attendees": e.attendees,
            "duration_hours": e.duration_hours,
            "meal_style": e.meal_style,
            "location_type": e.location_type,
            "season": e.season,
            "estimated_food": e.estimated_food_quantity,
            "actual_consumed": e.food_consumed,
            "surplus": e.food_surplus
        }
        for e in events
    ]
