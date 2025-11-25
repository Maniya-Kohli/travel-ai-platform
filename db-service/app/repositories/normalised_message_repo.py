"""
Normalised Message Repository
Database operations for Normalised Message model
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.normalised_message import  Normalised_Message
from sqlalchemy.dialects.postgresql import JSONB



class NormalisedMessageRepository:
    """Handles Normalised Message database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, thread_id: str, message_id : str ,  content: dict[str, any]) -> Normalised_Message:
        """
        Create a new Normalised message
        
        Args:
            thread_id: ID of the thread
            role: 'user' or 'assistant'
            content:dict
        """
        message = Normalised_Message(
            thread_id=thread_id,
            message_id=message_id,
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        print(f'Normalised_Message' , message)
        return message
    
    def get_by_id(self, message_id: str) -> Optional[Normalised_Message]:
        """Get Normalised message by ID"""
        return self.db.query(Normalised_Message).filter(Normalised_Message.id == message_id).first()
    
    def get_by_thread(
        self, 
        thread_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Normalised_Message]:
        """Get all Normalised messages in a thread"""
        return (
            self.db.query(Normalised_Message)
            .filter(Normalised_Message.thread_id == thread_id)
            .order_by(Normalised_Message.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def delete(self, normalised_message_id: str) -> bool:
        """Delete Normalised message by ID"""
        message = self.get_by_id(normalised_message_id)
        if message:
            self.db.delete(message)
            self.db.commit()
            return True
        return False
    
    def get_all(self, skip: int = 0, limit: int = 100) -> list[Normalised_Message]:
        return (
            self.db.query(Normalised_Message)
            .order_by(Normalised_Message.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )
