from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import ClassVar, Set, Dict


class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    DB_SERVICE_URL: str = "http://localhost:8001"
    OPENAI_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "worker-service"

    # All constants below should be annotated as ClassVar!
    DEFAULT_REGION_CODE: ClassVar[str] = "US-CA"
    DEFAULT_DESTINATION: ClassVar[dict] = {
        "type": "region", "name": "California, US", "region_code": "US-CA"
    }
    SUPPORTED_TRIP_TYPES: ClassVar[Set[str]] = {"TREKKING", "CAMPING", "ROAD_TRIP", "CITY_BREAK"}
    SUPPORTED_DIFFICULTY: ClassVar[Set[str]] = {"EASY", "MODERATE", "HARD"}
    SUPPORTED_TRAVEL_MODES: ClassVar[Set[str]] = {"CAR", "TRAIN", "BUS"}
    SUPPORTED_ACCOM: ClassVar[Set[str]] = {"CAMPING", "HOTEL", "HOSTEL"}
    SUPPORTED_AMENITIES: ClassVar[Set[str]] = {"WI_FI", "POOL", "PARKING"}
    BUDGET_BANDS: ClassVar[Dict[str, tuple]] = {
        "USD_0_500": (0, 500),
        "USD_500_1000": (500, 1000),
        "USD_1000_2000": (1000, 2000)
    }
    SHORT_WINDOW_MSG_COUNT: ClassVar[int] = 10  # context window size

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()
