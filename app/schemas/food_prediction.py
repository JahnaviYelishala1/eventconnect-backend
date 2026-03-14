from pydantic import BaseModel
from typing import List, Optional


class MenuItem(BaseModel):
    name: str
    category: Optional[str] = None
    food_type: Optional[str] = None


class FoodPredictionRequest(BaseModel):
    attendees: int
    meal_type: str
    items: List[MenuItem]