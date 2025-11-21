"""
Health Check Route
Simple endpoint to check if service is running
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "db-service"
    }
