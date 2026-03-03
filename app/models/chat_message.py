from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("event_bookings.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    booking = relationship("EventBooking")
    sender = relationship("User")