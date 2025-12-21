# app/repositories/message_repo.py
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.message import Message

class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, thread_id: str, role: str, content: str) -> Message:
        message = Message(
            thread_id=thread_id,
            role=role,
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_by_id(self, message_id: str) -> Optional[Message]:
        return self.db.query(Message).filter(Message.id == message_id).first()

    def get_by_thread(self, thread_id: str, skip: int = 0, limit: int = 100) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.thread_id == thread_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def delete(self, message_id: str) -> bool:
        message = self.get_by_id(message_id)
        if message:
            self.db.delete(message)
            self.db.commit()
            return True
        return False

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Message]:
        return (
            self.db.query(Message)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
