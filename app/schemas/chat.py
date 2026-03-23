from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    booking_id: int


class ChatResponse(BaseModel):
    reply: str
