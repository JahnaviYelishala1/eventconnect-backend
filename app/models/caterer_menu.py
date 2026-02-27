from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class CatererMenu(Base):
    __tablename__ = "caterer_menus"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterers.id"))

    item_name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    category = Column(String)  # Starter/Main/Dessert

    caterer = relationship("Caterer", back_populates="menus")