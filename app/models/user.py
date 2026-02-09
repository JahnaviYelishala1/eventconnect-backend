from sqlalchemy import Column, Integer, String
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
