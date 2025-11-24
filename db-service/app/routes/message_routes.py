# app/routes/message_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.repositories.message_repo import MessageRepository



router = APIRouter(prefix="/messages", tags=["messages"])

class MessageCreate(BaseModel):
    thread_id: str
    role: str           # 'user' or 'assistant'
    content: str

class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: str

    class Config:
        from_attributes = True

@router.post("", response_model=MessageResponse, status_code=201)
async def create_message(message: MessageCreate, db: Session = Depends(get_db)):
    repo = MessageRepository(db)
    msg = repo.create(
        thread_id=message.thread_id,
        role=message.role,
        content=message.content,
    )
    return MessageResponse(
        id=msg.id,
        thread_id=msg.thread_id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at.isoformat()
    )

@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(message_id: str, db: Session = Depends(get_db)):
    repo = MessageRepository(db)
    msg = repo.get_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageResponse(
        id=msg.id,
        thread_id=msg.thread_id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at.isoformat()
    )

@router.get("/thread/{thread_id}", response_model=List[MessageResponse])
async def get_thread_messages(thread_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    repo = MessageRepository(db)
    messages = repo.get_by_thread(thread_id, skip=skip, limit=limit)
    return [
        MessageResponse(
            id=msg.id,
            thread_id=msg.thread_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat()
        )
        for msg in messages
    ]
