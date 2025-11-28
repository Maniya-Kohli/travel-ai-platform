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
    thread_id: str
    message_id: str
    request_id: str
    dates: Optional[RawDates] = None
    destination: Optional[RawDestination] = None
    origin: Optional[RawDestination] = None
    user_filters: Optional[RawUserFilters] = None
    question: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    content : str


# ---------- Normalized shapes (what downstream relies on) ----------
class TimeBlock(BaseModel):
    start: Optional[date]
    end: Optional[date]
    days: Optional[int]
    nights: Optional[int]
    season_hint: Optional[Literal["WINTER", "SPRING", "SUMMER", "FALL"]] = None

class Transport(BaseModel):
    allowed: Optional[List[str]] = None
    forbidden: Optional[List[str]] = None
    intercity_travel: Optional[bool] = None


class LodgingPref(BaseModel):
    types: Optional[List[str]] = None
    pet_friendly_required: Optional[bool] = None
    amenities_prefer: Optional[List[str]] = None

class Budget(BaseModel):
    band: Optional[str]
    ceiling_total: Optional[int]
    per_day: Optional[int]

class Constraints(BaseModel):
    trip_types: Optional[List[str]] = None
    difficulty: Optional[Dict[str, str]] = None  # {"level": "EASY", "effort_profile": "LOW"}
    transport: Optional[Transport] = None
    lodging: Optional[LodgingPref] = None
    diet: Optional[List[str]] = None
    themes: Optional[List[str]] = None
    poi_tags: Optional[Dict[str, List[str]]] = None  
    budget: Optional[Budget] = None
    events_only: Optional[bool] = None


class GeoScope(BaseModel):
    destination: Optional[RawDestination] = None
    origin: Optional[RawDestination] = None
    in_scope_only: Optional[bool] = True                 # can be overridden / omitted
    out_of_scope: Optional[bool] = False                 # True if user asked outside CA
    original_destination: Optional[RawDestination] = None  # what user asked


class NormalizedMessage(BaseModel):
    type: Literal["normalized_message"] = "normalized_message"
    version: Literal["v1"] = "v1"

    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    time: Optional[TimeBlock] = None
    geoscope: Optional[GeoScope] = None
    constraints: Optional[Constraints] = None

    @field_validator("constraints")
    @classmethod
    def clamp_enums(cls, v: Optional[Constraints]) -> Optional[Constraints]:
        # If there are no constraints, nothing to clamp
        if v is None:
            return v

        # --- Trip types ---
        v.trip_types = [t for t in (v.trip_types or []) if t in S.SUPPORTED_TRIP_TYPES]

        # --- Difficulty ---
        # ensure difficulty is at least a dict
        if v.difficulty is None:
            v.difficulty = {}

        lvl = v.difficulty.get("level", "EASY")
        if lvl not in S.SUPPORTED_DIFFICULTY:
            # reset difficulty to safe defaults
            v.difficulty["level"] = "EASY"
            v.difficulty["effort_profile"] = "LOW"

        # --- Transport ---
        if v.transport is not None:
            v.transport.allowed = [
                m for m in (v.transport.allowed or [])
                if m in S.SUPPORTED_TRAVEL_MODES
            ]

        # --- Lodging ---
        if v.lodging is not None:
            v.lodging.types = [
                a for a in (v.lodging.types or [])
                if a in S.SUPPORTED_ACCOM
            ]
            v.lodging.amenities_prefer = [
                a for a in (v.lodging.amenities_prefer or [])
                if a in S.SUPPORTED_AMENITIES
            ]

        return v