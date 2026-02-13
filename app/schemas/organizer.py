from pydantic import BaseModel
from typing import Optional

class OrganizerCreate(BaseModel):
    full_name: str
    phone: str
    organization_name: Optional[str] = None
    city: str
    profile_image_url: Optional[str] = None

class OrganizerResponse(BaseModel):
    id: int
    full_name: str
    phone: str
    organization_name: Optional[str]
    city: str
    profile_image_url: Optional[str]

    class Config:
        from_attributes = True
