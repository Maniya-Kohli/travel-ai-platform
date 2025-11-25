# app/models/message.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from sqlalchemy.dialects.postgresql import JSONB


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, ForeignKey("threads.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 🔹 NEW: link back to Thread
    thread = relationship(
        "Thread",
        back_populates="messages",         # 👈 matches Thread.messages
    )

    normalised_message = relationship(
        "Normalised_Message",
        uselist=False,
        back_populates="message",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Message(id={self.id}, thread_id={self.thread_id}, message={self.message_id})>"
