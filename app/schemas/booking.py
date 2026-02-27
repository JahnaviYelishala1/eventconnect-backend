from pydantic import BaseModel
from typing import List

class BookingItemCreate(BaseModel):
    menu_id: int
    quantity: int

class BookingCreate(BaseModel):
    event_id: int
    caterer_id: int
    items: List[BookingItemCreate]

class BookingResponse(BaseModel):
    id: int
    event_id: int
    caterer_id: int
    status: str
    total_price: float

    class Config:
        from_attributes = True