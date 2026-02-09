from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from app.database import Base


class NGODocument(Base):
    __tablename__ = "ngo_documents"

    id = Column(Integer, primary_key=True)
    ngo_id = Column(Integer, ForeignKey("ngos.id"), nullable=False)

    document_type = Column(String, nullable=False)
    # REG_CERT | TRUST_DEED | PAN | 80G | 12A

    file_url = Column(String, nullable=False)
    status = Column(String, default="PENDING") 
    uploaded_at = Column(DateTime, default=datetime.utcnow)
