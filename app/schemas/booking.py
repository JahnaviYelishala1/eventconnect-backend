from datetime import date

from pydantic import BaseModel
from typing import List, Optional

class BookingItemCreate(BaseModel):
    menu_id: int
    quantity: int

class BookingCreate(BaseModel):
    event_id: int
    caterer_id: int
    items: List[BookingItemCreate]
    attendees: int          # ✅ NEW
    booking_date: date

class BookingItemDetail(BaseModel):
    menu_id: int
    item_name: str
    quantity: int
    price: float


class BookingResponse(BaseModel):
    id: int
    event_id: int
    caterer_id: int
    status: str
    total_price: float
    attendees: int
    booking_date: date

    caterer_name: Optional[str] = None
    event_name: Optional[str] = None

    items: List[BookingItemDetail] = []

    class Config:
        from_attributes = True
