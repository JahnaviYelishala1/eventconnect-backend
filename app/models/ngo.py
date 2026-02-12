from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.database import Base


class NGO(Base):
    __tablename__ = "ngos"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    registration_number = Column(String, nullable=False)
    email = Column(String, index=True, nullable=False)
    status = Column(
        String,
        default="PENDING"
        # PENDING | VERIFIED | REJECTED | SUSPENDED
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(Text, nullable=True)



