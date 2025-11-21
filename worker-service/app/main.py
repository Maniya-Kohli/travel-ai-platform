"""
Worker Service main loop.
Polls the Redis queue for trip requests and runs orchestration.
"""
import asyncio
from app.config import get_settings
from app.utils.queue_consumer import QueueConsumer
from app.orchestrator import TripOrchestrator

settings = get_settings()

async def worker_loop():
    queue = QueueConsumer(settings.REDIS_URL)
    orchestrator = TripOrchestrator()
    print("🚀 Worker Service started. Listening for trip requests...")

    while True:
        task = await queue.pop("trip_requests")
        if not task:
            await asyncio.sleep(1)
            continue

        print(f"Processing request {task['request_id']}")
        await orchestrator.process_trip_request(task)

if __name__ == "__main__":
    asyncio.run(worker_loop())
