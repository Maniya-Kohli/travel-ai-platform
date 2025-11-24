# app/models/normalized_trip.py
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from datetime import date
from pydantic import BaseModel, Field, field_validator
from app.config import get_settings

S = get_settings()  # pull enums/defaults from your centralized Settings


# Incoming RAW shapes (what the queue/gateway sends) 
class RawDates(BaseModel):
    start: Optional[date] = None
    end: Optional[date] = None

class RawUserFilters(BaseModel):
    trip_types: Optional[List[str]] = None
    difficulty: Optional[str] = None
    budget_level: Optional[str] = None
    duration_days: Optional[int] = None
    group_type: Optional[str] = None
    travel_modes: Optional[List[str]] = None
    accommodation: Optional[List[str]] = None
    accessibility: Optional[List[str]] = None
    meal_preferences: Optional[List[str]] = None
    must_include: Optional[List[str]] = None
    must_exclude: Optional[List[str]] = None
    interest_tags: Optional[List[str]] = None
    events_only: Optional[bool] = None
    amenities: Optional[List[str]] = None

class RawDestination(BaseModel):
    type: Literal["region", "city", "point"] = "region"
    name: Optional[str] = None
    region_code: Optional[str] = None

class RawRequest(BaseModel):
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    request_id: Optional[str] = None
    dates: Optional[RawDates] = None
    destination: Optional[RawDestination] = None
    origin: Optional[RawDestination] = None
    user_filters: Optional[RawUserFilters] = None
    question: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None


# ---------- Normalized shapes (what downstream relies on) ----------
class TimeBlock(BaseModel):
    start: date
    end: date
    days: int
    nights: int
    season_hint: Optional[Literal["WINTER", "SPRING", "SUMMER", "FALL"]] = None

class Transport(BaseModel):
    allowed: List[str]
    forbidden: List[str] = []
    intercity_travel: bool = False

class LodgingPref(BaseModel):
    types: List[str]
    pet_friendly_required: bool = False
    amenities_prefer: List[str] = []

class Budget(BaseModel):
    band: str
    ceiling_total: int
    per_day: int

class Constraints(BaseModel):
    trip_types: List[str]
    difficulty: Dict[str, str]  # {"level": "EASY", "effort_profile": "LOW"}
    transport: Transport
    lodging: LodgingPref
    diet: List[str] = []
    themes: List[str] = []
    poi_tags: Dict[str, List[str]] = {"must_include": [], "must_exclude": []}
    budget: Budget
    events_only: bool = False

class GeoScope(BaseModel):
    destination: RawDestination                      # effective destination (clamped to CA)
    origin: Optional[RawDestination] = None
    in_scope_only: bool = True                       # always True in v0
    out_of_scope: bool = False                       # True if user asked outside CA
    original_destination: Optional[RawDestination] = None  # what user asked


class NormalizedMessage(BaseModel):
    type: Literal["normalized_message"] = "normalized_message"
    version: Literal["v1"] = "v1"
    thread_id: str
    message_id: str
    time: TimeBlock
    geoscope: GeoScope
    constraints: Constraints

    @field_validator("constraints")
    @classmethod
    def clamp_enums(cls, v: Constraints):
        # Trip types
        v.trip_types = [t for t in v.trip_types or [] if t in S.SUPPORTED_TRIP_TYPES] or ["CAMPING"]
        # Difficulty
        lvl = (v.difficulty or {}).get("level", "EASY")
        if lvl not in S.SUPPORTED_DIFFICULTY:
            v.difficulty["level"] = "EASY"
            v.difficulty["effort_profile"] = "LOW"
        # Transport
        v.transport.allowed = [m for m in v.transport.allowed or [] if m in S.SUPPORTED_TRAVEL_MODES] or ["CAR"]
        # Lodging
        v.lodging.types = [a for a in v.lodging.types or [] if a in S.SUPPORTED_ACCOM] or ["CAMPING"]
        v.lodging.amenities_prefer = [a for a in v.lodging.amenities_prefer or [] if a in S.SUPPORTED_AMENITIES]
        return v
