from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("event_bookings.id"))

    stripe_payment_intent = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)

    payment_method = Column(String)
    card_brand = Column(String)
    card_last4 = Column(String)

    status = Column(String, default="paid")
    paid_at = Column(DateTime, default=datetime.utcnow)

    booking = relationship("EventBooking")
