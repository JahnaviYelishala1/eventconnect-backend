from pydantic import BaseModel


class NGOCreate(BaseModel):
    name: str
    registration_number: str


class NGOResponse(BaseModel):
    id: int
    name: str
    registration_number: str
    status: str

    class Config:
        from_attributes = True
