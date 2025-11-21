from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    DB_SERVICE_URL: str = "http://localhost:8001"
    OPENAI_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "worker-service"

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
