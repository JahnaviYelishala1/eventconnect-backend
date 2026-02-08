from pydantic import BaseModel

class FoodPredictionRequest(BaseModel):
    event_type: str
    attendees: int
    duration_hours: int
    meal_style: str
    location_type: str
    season: str


class FoodPredictionResponse(BaseModel):
    estimated_food_quantity: float
    unit: str = "kg"
