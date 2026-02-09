from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from app.database import Base


class EventLocation(Base):
    __tablename__ = "event_locations"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True   # 🔥 one location per event
    )

    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    pincode = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_type = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_location_event_id"),
    )
