from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)

    # 🔥 SUPPORT BOTH TYPES
    booking_id = Column(Integer, ForeignKey("event_bookings.id"), nullable=True)
    request_id = Column(Integer, ForeignKey("surplus_requests.id"), nullable=True)

    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender_role = Column(String, nullable=False)  # "ngo" / "organizer"

    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    booking = relationship("EventBooking")
    sender = relationship("User")