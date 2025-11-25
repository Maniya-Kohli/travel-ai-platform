# app/modules/request_handler.py
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
    return max(1, delta)  # clamp at least 1 day

def _season_hint(m: int) -> str:
    if m in (12, 1, 2):
        return "WINTER"
    if m in (3, 4, 5):
        return "SPRING"
    if m in (6, 7, 8):
        return "SUMMER"
    return "FALL"


class RequestHandler:
    """
    Validates and normalizes the raw request into a NormalizedMessage.
    """

    async def normalize(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        print('RAW REQUEST', raw_request)

        # ---- PATCH: Accept 'constraints' as alias for 'user_filters' ----
        if "constraints" in raw_request and "user_filters" not in raw_request:
            raw_request["user_filters"] = raw_request.pop("constraints")

        # 1) Parse raw request (tolerant of missing fields)
        try:
            raw = RawRequest.model_validate(raw_request or {})
        except ValidationError as ve:
            raise ValueError(f"Invalid request payload: {ve}") from ve

        # 2) Dates & duration
        start = raw.dates.start if (raw.dates and raw.dates.start) else date(2025, 12, 15)
        end = raw.dates.end if (raw.dates and raw.dates.end) else date(2025, 12, 20)
        days = _compute_days(start, end) or (raw.user_filters.duration_days if raw.user_filters and raw.user_filters.duration_days else 5)
        nights = days  # v0 simplification
        season = _season_hint(start.month if start else datetime.utcnow().month)

        time_block = TimeBlock(
            start=start,
            end=end,
            days=days,
            nights=nights,
            season_hint=season,
        )

        # 3) Destination default/clamp to California if missing
        dest = raw.destination
        out_of_scope = False
        orig_dest = None

        if not dest or dest.region_code != S.DEFAULT_REGION_CODE:
            out_of_scope = bool(dest)                       # user provided but not CA
            orig_dest = dest                                # remember what they asked
            dest = {
                "type": "region",
                "name": S.DEFAULT_DESTINATION["name"],
                "region_code": S.DEFAULT_REGION_CODE,
            }

        geoscope = GeoScope(
            destination=dest,
            origin=raw.origin,
            in_scope_only=True,                             # v0 constraint
            out_of_scope=out_of_scope,
            original_destination=orig_dest,
        )

        # 4) Constraints + defaults
        uf = raw.user_filters or None

        # difficulty → effort mapping (v0)
        diff_level = (uf.difficulty if uf and uf.difficulty else "EASY").upper()
        effort = "LOW" if diff_level == "EASY" else ("MEDIUM" if diff_level == "MODERATE" else "HIGH")

        # budget band → per-day ceiling heuristic
        band = (uf.budget_level if uf and uf.budget_level else "USD_0_500")
        lo, hi = S.BUDGET_BANDS.get(band, (0, 500))
        per_day = max(50, int(hi / max(1, days)))

        constraints = Constraints(
            trip_types=(uf.trip_types if uf and uf.trip_types else ["CAMPING"]),
            difficulty={"level": diff_level, "effort_profile": effort},
            transport=Transport(
                allowed=(uf.travel_modes if uf and uf.travel_modes else ["CAR"]),
                forbidden=(uf.must_exclude if uf and uf.must_exclude else []),
                intercity_travel=bool(raw.origin),
            ),
            lodging=LodgingPref(
                types=(uf.accommodation if uf and uf.accommodation else ["CAMPING"]),
                pet_friendly_required=("PET_FRIENDLY" in (uf.accessibility or []) if uf else False),
                amenities_prefer=(uf.amenities if uf and uf.amenities else []),
            ),
            diet=(uf.meal_preferences if uf and uf.meal_preferences else []),
            themes=(uf.interest_tags if uf and uf.interest_tags else []),
            poi_tags={
                "must_include": (uf.must_include if uf and uf.must_include else []),
                "must_exclude": (uf.must_exclude if uf and uf.must_exclude else []),
            },
            budget=Budget(band=band, ceiling_total=hi, per_day=per_day),
            events_only=(bool(uf.events_only) if (uf and uf.events_only is not None) else False),
        )

        # 5) Final normalized message (Pydantic will clamp enums via validator)
        nm = NormalizedMessage(
            thread_id=raw.thread_id or "t_unknown",
            message_id=raw.message_id or "m_unknown",
            time=time_block,
            geoscope=geoscope,
            constraints=constraints,
        )

        return nm
