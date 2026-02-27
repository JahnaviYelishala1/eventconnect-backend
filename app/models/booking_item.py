from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class BookingItem(Base):
    __tablename__ = "booking_items"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("event_bookings.id"))
    menu_id = Column(Integer, ForeignKey("caterer_menus.id"))

    quantity = Column(Integer, nullable=False)

    booking = relationship("EventBooking", back_populates="items")