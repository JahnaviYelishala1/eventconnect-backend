from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class CatererService(Base):
    __tablename__ = "caterer_services"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterers.id"))

    service_type = Column(String, nullable=False)

    caterer = relationship("Caterer", back_populates="services")
