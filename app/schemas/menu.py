from pydantic import BaseModel
from typing import Optional

class MenuCreate(BaseModel):
    item_name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    food_type: str
    image_url: Optional[str] = None 

class MenuResponse(MenuCreate):
    id: int

    class Config:
        from_attributes = True