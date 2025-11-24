"""
Normalised Message Repository
Database operations for Normalised Message model
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.message import Message
from sqlalchemy.dialects.postgresql import JSONB



class NormalisedMessageRepository:
    """Handles Normalised Message database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, thread_id: str, role: str,  content: dict[str, any]) -> Message:
        """
        Create a new Normalised message
        
        Args:
            thread_id: ID of the thread
            role: 'user' or 'assistant'
            content:dict
        """
        message = Message(
            thread_id=thread_id,
            role=role,
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        print(f'MESSAGE' , message)
        return message
    
    def get_by_id(self, message_id: str) -> Optional[Message]:
        """Get Normalised message by ID"""
        return self.db.query(Message).filter(Message.id == message_id).first()
    
    def get_by_thread(
        self, 
        thread_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Message]:
        """Get all Normalised messages in a thread"""
        return (
            self.db.query(Message)
            .filter(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def delete(self, message_id: str) -> bool:
        """Delete Normalised message by ID"""
        message = self.get_by_id(message_id)
        if message:
            self.db.delete(message)
            self.db.commit()
            return True
        return False
