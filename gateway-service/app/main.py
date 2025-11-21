from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes import health, trip_request

settings = get_settings()

app = FastAPI(
    title="Travel AI Gateway Service",
    description="Frontend API for Travel AI platform",
    version="1.0.0",
    docs_url="/docs"
)

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

