from pydantic import BaseModel
from typing import List


class MenuItem(BaseModel):
    name: str
    category: str


class FoodPredictionRequest(BaseModel):
    attendees: int
    meal_type: str
    items: List[MenuItem]