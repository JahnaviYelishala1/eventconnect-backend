from pydantic import BaseModel
from typing import List, Optional

class CatererCreate(BaseModel):
    business_name: str
    city: str
    min_capacity: int
    max_capacity: int
    price_per_plate: float
    veg_supported: bool
    nonveg_supported: bool
    latitude: float
    longitude: float
    services: List[str]
    image_url: Optional[str] = None

class CatererServiceResponse(BaseModel):
    service_type: str

    class Config:
        from_attributes = True

class CatererResponse(BaseModel):
    id: int
    business_name: str
    city: str
    min_capacity: int
    max_capacity: int
    price_per_plate: float
    veg_supported: bool
    nonveg_supported: bool
    rating: float
    latitude: float
    longitude: float
    image_url: Optional[str] = None
    distance_km: float
    services: List[CatererServiceResponse] = []

    class Config:
        from_attributes = True



