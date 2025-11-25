from pydantic import BaseModel
from app.config import get_settings
from app.utils.queue_producer import QueueProducer
from fastapi import APIRouter, HTTPException, Query
from app.clients.db_service_client import DBServiceClient

import logging

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/trip", tags=["trip"])


class TripRequest(BaseModel):
    request_id: str
    thread_id: str
    message_id: str
    constraints: dict
    content: str




@router.post("/plan")
async def submit_trip_request(request: TripRequest):
    """
    Enqueue a trip planning request to Redis.
    Worker service will consume 'trip_requests'.
    """
    logger.info(
        "TRIP /plan: received request",
        extra={
            "request_id": request.request_id,
            "thread_id": request.thread_id,
            "message_id": request.message_id,
        },
    )

    try:
        qp = QueueProducer(settings.REDIS_URL)
        logger.debug(
            "TRIP /plan: pushing to Redis queue",
            extra={
                "redis_url": settings.REDIS_URL,
                "queue": "trip_requests",
                "request_id": request.request_id,
            },
        )
        qp.push("trip_requests", request.dict())
        logger.info(
            "TRIP /plan: successfully enqueued request",
            extra={"request_id": request.request_id},
        )
        return {"status": "queued", "request_id": request.request_id}
    except Exception as e:
        logger.exception(
            "TRIP /plan: failed to enqueue request",
            extra={
                "request_id": request.request_id,
                "thread_id": request.thread_id,
                "message_id": request.message_id,
            },
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to enqueue trip request: {e}"
        )


@router.get("/latest")
async def get_latest_reply(thread_id: str = Query(...)):
    """
    Returns the latest assistant message in a thread (if any).
    Used by frontend polling.
    """
    db = DBServiceClient()   

    try:
        msgs = await db.get_thread_messages(thread_id=thread_id, skip=0, limit=100)
        assistants = [m for m in msgs if m.get("role") == "assistant"]

        if not assistants:
            return {"status": "pending", "message": None}

        latest = sorted(
            assistants,
            key=lambda m: m.get("created_at") or "",
            reverse=True,
        )[0]

        return {
            "status": "ok",
            "message": latest,
        }

    except Exception as e:
        pass
    finally:
        await db.close()
