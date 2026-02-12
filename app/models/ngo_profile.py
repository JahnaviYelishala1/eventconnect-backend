from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class NGOProfile(Base):
    __tablename__ = "ngo_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    name = Column(String)
    established_year = Column(String)
    about = Column(String)
    email = Column(String)
    phone = Column(String)
    address = Column(String)

    latitude = Column(Float)
    longitude = Column(Float)
    image_url = Column(String)

    user = relationship("User")
