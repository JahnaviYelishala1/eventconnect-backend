from pydantic import BaseModel
from typing import List

class CatererCreate(BaseModel):
    business_name: str
    city: str
    min_capacity: int
    max_capacity: int
    price_per_plate: float
    veg_supported: bool
    nonveg_supported: bool
    services: List[str]


class CatererResponse(BaseModel):
    id: int
    business_name: str
    city: str
    price_per_plate: float
    rating: float

    class Config:
        from_attributes = True
