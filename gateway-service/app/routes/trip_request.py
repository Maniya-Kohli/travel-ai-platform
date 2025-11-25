from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config import get_settings
from app.utils.queue_producer import QueueProducer

import logging
logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/trip", tags=["trip"])

class TripRequest(BaseModel):
    request_id: str
    thread_id: str
    message_id : str
    constraints: dict
    content : str

@router.post("/plan")
async def submit_trip_request(request: TripRequest):
    logger.info(f"Received trip request: {request}")
    qp = QueueProducer(settings.REDIS_URL)
    qp.push("trip_requests", request.dict())
    return {"status": "queued", "request_id": request.request_id}
