from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config import get_settings
from app.utils.queue_producer import QueueProducer

settings = get_settings()
router = APIRouter(prefix="/trip", tags=["trip"])

class TripRequest(BaseModel):
    request_id: str
    thread_id: str
    constraints: dict

@router.post("/plan")
async def submit_trip_request(request: TripRequest):
    qp = QueueProducer(settings.REDIS_URL)
    qp.push("trip_requests", request.dict())
    return {"status": "queued", "request_id": request.request_id}
