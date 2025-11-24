"""
Normalised Message Model
message for downstream processing 
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from sqlalchemy.dialects.postgresql import JSONB



class Normalised_Message(Base):
    
    __tablename__ = "normalised_message"
    
    # Columns
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, ForeignKey("threads.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"
