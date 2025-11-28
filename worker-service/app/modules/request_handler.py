from datetime import datetime, date
from typing import Any, Dict, Optional

from pydantic import ValidationError

from app.config import get_settings
from app.models.normalized_trip import (
    RawRequest,
    NormalizedMessage,
    TimeBlock,
    GeoScope,
    Constraints,
    Transport,
    LodgingPref,
    Budget,
)

S = get_settings()


def _compute_days(start_d: Optional[date], end_d: Optional[date]) -> Optional[int]:
    if not start_d or not end_d:
        return None
    delta = (end_d - start_d).days
    # If user gave an end before start, clamp at 1 so we don't break downstream.
    return max(1, delta) if delta > 0 else 1


def _season_hint(m: Optional[int]) -> Optional[str]:
    if m is None:
        return None
    if m in (12, 1, 2):
        return "WINTER"
    if m in (3, 4, 5):
        return "SPRING"
    if m in (6, 7, 8):
        return "SUMMER"
    return "FALL"


class RequestHandler:
    """
    Validates and normalizes the raw request into a NormalizedMessage,
    without injecting semantic defaults.

    - If the user doesn't provide something (dates, budget, trip_types, etc.)
      we leave it as None or [].
    - We NEVER override user-provided values with "smart" defaults.
    """

    async def normalize(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        print("RAW REQUEST", raw_request)

        # ---- PATCH: Accept 'constraints' as alias for 'user_filters' ----
        if "constraints" in raw_request and "user_filters" not in raw_request:
            raw_request["user_filters"] = raw_request.pop("constraints")

        # 1) Parse raw request (tolerant of missing fields)
        raw = RawRequest.model_validate(raw_request or {})

        uf = raw.user_filters or None

        # 2) Dates & duration (NO hard-coded defaults)
        start: Optional[date] = raw.dates.start if (raw.dates and raw.dates.start) else None
        end: Optional[date] = raw.dates.end if (raw.dates and raw.dates.end) else None

        # Prefer explicit start/end to derive days; otherwise fall back to user duration_days.
        days: Optional[int] = _compute_days(start, end)
        if days is None and uf and uf.duration_days:
            days = uf.duration_days

        nights: Optional[int] = days  # simple v0: nights ~= days
        season = _season_hint(start.month if start else None)

        time_block = TimeBlock(
            start=start,
            end=end,
            days=days,
            nights=nights,
            season_hint=season,
        )

        # 3) Destination: DO NOT override with California defaults
        dest = raw.destination
        out_of_scope = False
        orig_dest = None

        # If your product is "California-only", you can *flag* out-of-scope,
        # but do not override the actual destination the user gave.
        if dest and dest.region_code != S.DEFAULT_REGION_CODE:
            out_of_scope = True
            orig_dest = dest  # keep what they asked for

        geoscope = GeoScope(
            destination=dest,
            origin=raw.origin,
            # If you want in-scope-only behavior, depend on destination actually being CA.
            in_scope_only=bool(dest and dest.region_code == S.DEFAULT_REGION_CODE),
            out_of_scope=out_of_scope,
            original_destination=orig_dest,
        )

        # 4) Constraints (user over everything, no semantic defaults)
        # difficulty → effort mapping (derived from user input only)
        diff_level: Optional[str] = None
        effort: Optional[str] = None
        if uf and uf.difficulty:
            diff_level = uf.difficulty.upper()
            if diff_level == "EASY":
                effort = "LOW"
            elif diff_level in ("MODERATE", "MEDIUM"):
                effort = "MEDIUM"
            else:
                effort = "HIGH"

        # Budget: only derive numbers if user gave a band
        budget_obj: Optional[Budget] = None
        if uf and uf.budget_level:
            band = uf.budget_level
            lo_hi = S.BUDGET_BANDS.get(band)
            ceiling_total: Optional[int] = None
            per_day: Optional[int] = None

            if lo_hi is not None:
                lo, hi = lo_hi
                ceiling_total = hi
                if hi is not None and days:
                    per_day = max(1, int(hi / max(1, days)))

            budget_obj = Budget(
                band=band,
                ceiling_total=ceiling_total,
                per_day=per_day,
            )

        # Build constraints from user filters only; everything else empty/None
        constraints = Constraints(
            trip_types=(uf.trip_types if uf and uf.trip_types else []),
            difficulty=(
                {"level": diff_level, "effort_profile": effort}
                if diff_level is not None or effort is not None
                else None
            ),
            transport=Transport(
                allowed=(uf.travel_modes if uf and uf.travel_modes else []),
                forbidden=(uf.must_exclude if uf and uf.must_exclude else []),
                # This is a pure derivation from origin, not a semantic default.
                intercity_travel=bool(raw.origin),
            ),
            lodging=LodgingPref(
                types=(uf.accommodation if uf and uf.accommodation else []),
                pet_friendly_required=(
                    "PET_FRIENDLY" in (uf.accessibility or []) if uf else False
                ),
                amenities_prefer=(uf.amenities if uf and uf.amenities else []),
            ),
            diet=(uf.meal_preferences if uf and uf.meal_preferences else []),
            themes=(uf.interest_tags if uf and uf.interest_tags else []),
            poi_tags={
                "must_include": (uf.must_include if uf and uf.must_include else []),
                "must_exclude": (uf.must_exclude if uf and uf.must_exclude else []),
            },
            budget=budget_obj,
            # Preserve exactly what the user said; don't coerce False/True if it's None.
            events_only=(uf.events_only if (uf and uf.events_only is not None) else None),
        )

        # 5) Final normalized message
        nm = NormalizedMessage(
            thread_id=raw.thread_id ,
            message_id=raw.message_id ,
            time=time_block,
            geoscope=geoscope,
            constraints=constraints,
        )

        # Return as dict for downstream usage
        print('normlaised message' , nm)
        return nm

       