from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field


class SurplusCreate(BaseModel):

    event_id: int
    food_description: str = Field(
        validation_alias=AliasChoices("food_description", "description")
    )
    image_url: str | None = None

    latitude: float
    longitude: float


class SurplusAlertResponse(BaseModel):

    request_id: int
    message: str


class SurplusNgoResponse(BaseModel):

    id: int
    ngo_name: str
    phone: str


class SurplusResponse(BaseModel):

    id: int
    event_id: int
    food_description: str
    image_url: Optional[str] = None

    latitude: float
    longitude: float

    status: str

    class Config:
        from_attributes = True


class SurplusAcceptedResponse(BaseModel):
    request_id: int
    event_id: int
    organizer_id: int
    event_name: str
    food_description: str
    image_url: Optional[str]
    latitude: float
    longitude: float
    status: str
    accepted_by_ngo: Optional[int]
    created_at: datetime
    organizer_name: Optional[str] = None
    organizer_phone: Optional[str] = None