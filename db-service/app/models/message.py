# app/models/message.py
from datetime import datetime
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, ForeignKey("threads.id"), nullable=False)
    role = Column(String, nullable=False)

    # JSONB so we can store either plain text or structured JSON
    content = Column(JSONB, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 🔹 Link back to Thread (one-to-many: Thread → Messages)
    thread = relationship(
        "Thread",
        back_populates="messages",  # must match Thread.messages
    )

    # 🔹 One-to-one to Normalised_Message (optional)
    normalised_message = relationship(
        "Normalised_Message",
        uselist=False,
        back_populates="message",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        # Safe preview of content for logs/debugging
        try:
            preview = None
            if isinstance(self.content, str):
                preview = self.content[:60]
            else:
                # for dict / list / other JSON-ish
                preview = str(self.content)[:60]
        except Exception:
            preview = "<unavailable>"

        return (
            f"<Message(id={self.id}, "
            f"thread_id={self.thread_id}, "
            f"role={self.role}, "
            f"content_preview={preview})>"
        )
