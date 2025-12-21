"""
DB Service - Main Application
FastAPI app for database access layer
"""
import os
import logging
import debugpy

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes.health import router as health
from app.routes.thread_routes import router as thread_routes
from app.routes.message_routes import router as message_routes
from app.routes.normalised_message_routes import router as normalised_message_routes
from app.routes.vectordb_routes import router as vectordb_routes
from platform_common.logging_config import init_logging
from app.routes.seed_routes import router as seed_router



# 🔧 Optional debugpy attach (controlled by env vars)
if os.getenv("ENABLE_DEBUGPY", "0") == "1":
    try:
       

        debug_port = int(os.getenv("DEBUGPY_PORT", "5679"))
        print(f"🔧 [db-service] Waiting for debugger attach on 0.0.0.0:{debug_port}...")
        debugpy.listen(("0.0.0.0", debug_port))
        # debugpy.wait_for_client()
        print("✅ [db-service] Debugger attached!")
    except Exception as e:
        print(f"⚠️ [db-service] Failed to start debugpy: {e}")


settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Travel AI - DB Service",
    description="Database access layer for Travel AI Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (allow other services to call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_logging("db-service")
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# Register routes
app.include_router(health)
app.include_router(thread_routes)
app.include_router(message_routes)
app.include_router(normalised_message_routes)
app.include_router(vectordb_routes)
app.include_router(seed_router)



@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    print("🚀 Starting DB Service...")
    print(f"📍 Environment: {settings.ENVIRONMENT}")
    print(f"🔗 Database: {settings.DATABASE_URL.split('@')[1]}")  # Hide password

    # Create tables if they don't exist
    init_db()

    print(f"✅ DB Service ready on port {settings.SERVICE_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("👋 Shutting down DB Service...")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "db-service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
