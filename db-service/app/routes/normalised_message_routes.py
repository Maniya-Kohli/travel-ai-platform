"""
Normalised Message Routes
API endpoints for message operations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.repositories.normalised_message_repo import NormalisedMessageRepository
from pydantic import BaseModel
from typing import Any, Dict


router = APIRouter(prefix="/normalised_messages", tags=["normalised_messages"])


# Request/Response schemas
class NormalisedMessageCreate(BaseModel):
    thread_id: str
    role: str
    content: Dict[str, Any]

class NormalisedMessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: Dict[str, Any]
    created_at: str

    class Config:
        from_attributes = True



@router.post("", response_model=NormalisedMessageResponse, status_code=201)
async def create_message(
    message: NormalisedMessageCreate,
    db: Session = Depends(get_db)
):
    """Create a new Normalised message in a thread"""
    repo = NormalisedMessageRepository(db)
    msg = repo.create(
        thread_id=message.thread_id,
        role=message.role,
        content=message.content
    )
    
    return NormalisedMessageResponse(
        id=msg.id,
        thread_id=msg.thread_id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at.isoformat()
    )


@router.get("/{message_id}", response_model=NormalisedMessageResponse)
async def get_message(message_id: str, db: Session = Depends(get_db)):
    """Get message by ID"""
    repo = NormalisedMessageRepository(db)
    message = repo.get_by_id(message_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Normalised Message not found")
    
    return NormalisedMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat()
    )

