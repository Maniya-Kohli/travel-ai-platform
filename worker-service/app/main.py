"""
Worker Service main loop.
Polls the Redis queue for trip requests and runs orchestration.
"""
import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import asyncio
import signal
from app.config import get_settings
from app.utils.queue_consumer import QueueConsumer
from app.orchestrator import TripOrchestrator
from platform_common.logging_config import init_logging

import logging

# 🔧 Optional debugpy attach (controlled by env vars)
if os.getenv("ENABLE_DEBUGPY", "0") == "1":
    try:
        import debugpy

        debug_port = int(os.getenv("DEBUGPY_PORT", "5680"))
        print(f"🔧 [worker-service] Waiting for debugger attach on 0.0.0.0:{debug_port}...")
        debugpy.listen(("0.0.0.0", debug_port))
        debugpy.wait_for_client()
        print("✅ [worker-service] Debugger attached!")
    except Exception as e:
        print(f"⚠️ [worker-service] Failed to start debugpy: {e}")

settings = get_settings()
orchestrator = TripOrchestrator()
running = True

init_logging("worker-service")
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

# 🔇 Quiet noisy libraries
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)


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
            # Log full traceback for debugging
            logger.exception("❌ Worker error while processing request")
            print(f"❌ Worker error: {e}")
            await asyncio.sleep(5)  # Backoff on error

    # Cleanup
    await orchestrator.close()


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    asyncio.run(worker_loop())
