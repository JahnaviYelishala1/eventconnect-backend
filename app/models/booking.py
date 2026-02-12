from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(Integer, ForeignKey("events.id"))
    caterer_id = Column(Integer, ForeignKey("users.id"))

    status = Column(String, default="PENDING")
    # PENDING | ACCEPTED | REJECTED

    event = relationship("Event")
    caterer = relationship("User")
