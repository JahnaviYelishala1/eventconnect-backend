from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Organizer(Base):
    __tablename__ = "organizers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    organization_name = Column(String, nullable=True)
    city = Column(String, nullable=False)
    profile_image_url = Column(String, nullable=True)

    user = relationship("User")
