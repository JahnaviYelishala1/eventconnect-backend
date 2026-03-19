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
    image_url: str

    latitude: float
    longitude: float

    status: str

    class Config:
        from_attributes = True