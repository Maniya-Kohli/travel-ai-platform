"""
Worker Service main loop.
Polls the Redis queue for trip requests and runs orchestration.
"""
import sys
sys.stdout.reconfigure(line_buffering=True)

import asyncio
import signal
from app.config import get_settings
from app.utils.queue_consumer import QueueConsumer
from app.orchestrator import TripOrchestrator

settings = get_settings()
orchestrator = TripOrchestrator()
running = True


def handle_shutdown(signum, frame):
    """Handle graceful shutdown"""
    global running
    print("\n👋 Shutting down worker service...")
    running = False


async def worker_loop():
    queue = QueueConsumer(settings.REDIS_URL)
    print("🚀 Worker Service started. Listening for trip requests...")

    while running:
        try:
            task = await queue.pop("trip_requests")
            if not task:
                await asyncio.sleep(1)
                continue

            print(f"\n📨 Processing request {task.get('request_id')}")
            await orchestrator.process_trip_request(task)
            print(f"✅ Request {task.get('request_id')} completed\n")
            
        except Exception as e:
            print(f"❌ Worker error: {e}")
            await asyncio.sleep(5)  # Backoff on error
    
    # Cleanup
    await orchestrator.close()


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    asyncio.run(worker_loop())
