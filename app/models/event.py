# app/models/event.py

from sqlalchemy import Column, Integer, String, Float
from app.database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String, index=True, nullable=False)

    event_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    attendees = Column(Integer, nullable=False)
    duration_hours = Column(Integer, nullable=False)
    meal_style = Column(String, nullable=False)
    location_type = Column(String, nullable=False)
    season = Column(String, nullable=False)

    estimated_food_quantity = Column(Float, nullable=False)
    unit = Column(String, default="kg")

    # ✅ NEW FIELDS
    food_prepared = Column(Float, nullable=True)
    food_consumed = Column(Float, nullable=True)
    food_surplus = Column(Float, nullable=True)
    booking_status = Column(String, nullable=True)
