"""
DB Service - Main Application
FastAPI app for database access layer
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
from app.routes import health, thread_routes, message_routes

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Travel AI - DB Service",
    description="Database access layer for Travel AI Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (allow other services to call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router)
app.include_router(thread_routes.router)
app.include_router(message_routes.router)


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
        "docs": "/docs"
    }
