"""
Database connection setup
Creates SQLAlchemy engine and session
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Check connections before using
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes
    Provides database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database
    Create all tables
    """
    # Import models so they're registered
    from app.models import thread, message , normalised_message
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")
