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
    message_id : str 
    content: Dict[str, Any]

class NormalisedMessageResponse(BaseModel):
    thread_id: str
    message_id : str 
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
        message_id = message.message_id,
        content=message.content
    )
    
    return NormalisedMessageResponse(
        message_id=msg.message_id,
        thread_id=msg.thread_id,
        content=msg.content,
        created_at=msg.created_at.isoformat()
    )


@router.get("/{normlalised_message_id}", response_model=NormalisedMessageResponse)
async def get_message(normlalised_message_id: str, db: Session = Depends(get_db)):
    """Get message by ID"""
    repo = NormalisedMessageRepository(db)
    message = repo.get_by_id(normlalised_message_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Normalised Message not found")
    
    return NormalisedMessageResponse(
        message_id=message.message_id,
        thread_id=message.thread_id,
        content=message.content,
        created_at=message.created_at.isoformat()
    )

@router.get("", response_model=List[NormalisedMessageResponse])
async def list_normalised_messages(
    thread_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all normalised messages. Optionally filter by thread_id. Supports pagination.
    """
    repo = NormalisedMessageRepository(db)
    if thread_id:
        messages = repo.get_by_thread(thread_id, skip=skip, limit=limit)
    else:
        messages = repo.get_all()
    return [
        NormalisedMessageResponse(
            message_id=m.message_id,
            thread_id=m.thread_id,
            content=m.content,
            created_at=m.created_at.isoformat()
        )
        for m in messages
    ]


