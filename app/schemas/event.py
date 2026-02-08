from pydantic import BaseModel

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

    class Config:
        from_attributes = True