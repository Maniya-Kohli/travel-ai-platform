"""
Thread Routes
API endpoints for thread operations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.repositories.thread_repo import ThreadRepository
from pydantic import BaseModel

router = APIRouter(prefix="/threads", tags=["threads"])


# Response schemas
class ThreadResponse(BaseModel):
    id: str
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(db: Session = Depends(get_db)):
    """Create a new conversation thread"""
    repo = ThreadRepository(db)
    thread = repo.create()
    return ThreadResponse(
        id=thread.id,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat()
    )


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: str, db: Session = Depends(get_db)):
    """Get thread by ID"""
    repo = ThreadRepository(db)
    thread = repo.get_by_id(thread_id)
    
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return ThreadResponse(
        id=thread.id,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat()
    )


@router.get("", response_model=List[ThreadResponse])
async def list_threads(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all threads with pagination"""
    repo = ThreadRepository(db)
    threads = repo.get_all(skip=skip, limit=limit)
    
    return [
        ThreadResponse(
            id=thread.id,
            created_at=thread.created_at.isoformat(),
            updated_at=thread.updated_at.isoformat()
        )
        for thread in threads
    ]


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, db: Session = Depends(get_db)):
    """Delete thread by ID"""
    repo = ThreadRepository(db)
    success = repo.delete(thread_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return None
