from sqlalchemy import Column, Date, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class EventBooking(Base):
    __tablename__ = "event_bookings"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(Integer, ForeignKey("events.id"))
    caterer_id = Column(Integer, ForeignKey("caterers.id"))
    organizer_id = Column(Integer, ForeignKey("users.id"))  # ✅ Added

    status = Column(String, default="pending")
    total_price = Column(Float, default=0)
    attendees = Column(Integer)          # ✅ NEW
    booking_date = Column(Date)          # ✅ NEW

    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship(
        "BookingItem",
        back_populates="booking",
        cascade="all, delete-orphan"
    )