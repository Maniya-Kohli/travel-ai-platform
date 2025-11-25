from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    SERVICE_PORT: int = 8000
    REDIS_URL: str = "redis://redis:6379"
    ENVIRONMENT: str = "development"
    DB_SERVICE_URL: str = "http://localhost:8001"

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
