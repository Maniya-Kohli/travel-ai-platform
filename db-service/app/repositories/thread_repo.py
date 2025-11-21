"""
Thread Repository
Database operations for Thread model
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.thread import Thread


class ThreadRepository:
    """Handles Thread database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self) -> Thread:
        """Create a new thread"""
        thread = Thread()
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)
        return thread
    
    def get_by_id(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID"""
        return self.db.query(Thread).filter(Thread.id == thread_id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Thread]:
        """Get all threads with pagination"""
        return self.db.query(Thread).offset(skip).limit(limit).all()
    
    def delete(self, thread_id: str) -> bool:
        """Delete thread by ID"""
        thread = self.get_by_id(thread_id)
        if thread:
            self.db.delete(thread)
            self.db.commit()
            return True
        return False
