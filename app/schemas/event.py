from pydantic import BaseModel
from typing import Optional
from app.schemas.event_location import EventLocationCreate


class EventCreate(BaseModel):
    event_name: str
    event_type: str
    attendees: int
    duration_hours: int
    meal_style: str
    location_type: str
    season: str


class EventResponse(BaseModel):
    id: int
    event_name: str
    event_type: str
    attendees: int
    duration_hours: int
    meal_style: str
    location_type: str
    season: str
    estimated_food_quantity: float
    unit: str
    food_prepared: Optional[float]
    food_consumed: Optional[float]
    food_surplus: Optional[float]
    status: str

    class Config:
        from_attributes = True


class EventComplete(BaseModel):
    food_prepared: float
    food_consumed: float
    surplus_location: Optional[EventLocationCreate] = None
