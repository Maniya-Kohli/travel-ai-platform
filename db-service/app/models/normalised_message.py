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

    # Shared PK/FK with messages.id
    message_id = Column(String, ForeignKey("messages.id"), primary_key=True)
    thread_id = Column(String, nullable=False)  
    content = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="normalised_message")

    def __repr__(self):
        return f"<Normalised_Message(message_id={self.message_id}>"
