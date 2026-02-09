from pydantic import BaseModel

class EventLocationCreate(BaseModel):
    address: str
    city: str
    pincode: str
    latitude: float | None = None
    longitude: float | None = None
    location_type: str
