from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class CatererMealStyle(Base):
    __tablename__ = "caterer_meal_styles"

    id = Column(Integer, primary_key=True, index=True)
    caterer_id = Column(Integer, ForeignKey("caterers.id"))
    meal_style = Column(String, nullable=False)

    caterer = relationship("Caterer", back_populates="meal_styles")