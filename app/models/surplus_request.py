from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SurplusRequest(Base):

    __tablename__ = "surplus_requests"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(Integer, ForeignKey("events.id"))
    organizer_id = Column(Integer, ForeignKey("users.id"))

    food_description = Column(String)
    image_url = Column(String)

    latitude = Column(Float)
    longitude = Column(Float)

    accepted_by_ngo = Column(Integer, ForeignKey("ngos.id"), nullable=True)

    status = Column(String, default="OPEN")

    created_at = Column(DateTime, default=datetime.utcnow)