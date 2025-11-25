from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes import health, trip_request
from platform_common.logging_config import init_logging
import logging

settings = get_settings()

app = FastAPI(
    title="Travel AI Gateway Service",
    description="Frontend API for Travel AI platform",
    version="1.0.0",
    docs_url="/docs"
)


init_logging("gateway-service")
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
# 🔇 quiet noisy libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING) 


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(health.router)
app.include_router(trip_request.router)

@app.get("/")
async def root():
    return {"service": "gateway-service", "status": "running"}

