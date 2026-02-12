from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Caterer(Base):
    __tablename__ = "caterers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    business_name = Column(String, nullable=False)
    city = Column(String, nullable=False)

    min_capacity = Column(Integer, nullable=False)
    max_capacity = Column(Integer, nullable=False)

    price_per_plate = Column(Float, nullable=False)

    veg_supported = Column(Boolean, default=True)
    nonveg_supported = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)

    rating = Column(Float, default=4.0)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)


    user = relationship("User")
    services = relationship("CatererService", back_populates="caterer")
