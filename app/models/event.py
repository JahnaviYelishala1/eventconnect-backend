from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    # Firebase user
    firebase_uid = Column(String, index=True, nullable=False)

    # Event details
    event_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    attendees = Column(Integer, nullable=False)
    duration_hours = Column(Integer, nullable=False)
    meal_style = Column(String, nullable=False)
    location_type = Column(String, nullable=False)
    season = Column(String, nullable=False)

    # ML prediction
    estimated_food_quantity = Column(Float, nullable=False)
    unit = Column(String, default="kg")
