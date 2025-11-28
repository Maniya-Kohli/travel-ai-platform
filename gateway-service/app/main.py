import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import health, trip_request
from platform_common.logging_config import init_logging

# 🔧 Optional debugpy attach (controlled by env vars)
if os.getenv("ENABLE_DEBUGPY", "0") == "1":
    try:
        import debugpy

        debug_port = int(os.getenv("DEBUGPY_PORT", "5678"))
        print(f"🔧 [gateway-service] Waiting for debugger attach on 0.0.0.0:{debug_port}...")
        debugpy.listen(("0.0.0.0", debug_port))
        debugpy.wait_for_client()
        print("✅ [gateway-service] Debugger attached!")
    except Exception as e:
        print(f"⚠️ [gateway-service] Failed to start debugpy: {e}")

settings = get_settings()

app = FastAPI(
    title="Travel AI Gateway Service",
    description="Frontend API for Travel AI platform",
    version="1.0.0",
    docs_url="/docs",
)

init_logging("gateway-service")
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

# 🔇 quiet noisy libs
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(trip_request.router)


@app.get("/")
async def root():
    return {"service": "gateway-service", "status": "running"}
