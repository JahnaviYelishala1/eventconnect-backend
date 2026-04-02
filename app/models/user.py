from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    firebase_uid = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)

    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    role = Column(String, nullable=False, default="UNASSIGNED")
    # UNASSIGNED | event_organizer | caterer | ngo

    password_hash = Column(String, nullable=True)
    reset_token = Column(String, nullable=True, index=True)
    reset_token_expiry = Column(DateTime, nullable=True)

    fcm_token = Column(Text, nullable=True)  # Firebase Cloud Messaging token for push notifications
