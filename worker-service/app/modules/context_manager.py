# app/modules/context_manager.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import re
from copy import deepcopy

from app.config import get_settings
from app.clients.db_service_client import DBServiceClient

logger = logging.getLogger(__name__)
S = get_settings()

# ----------------------------------------
# Regex helpers (chat → anchors extraction)
# ----------------------------------------

_TIME_RE = re.compile(
    r"\b(?:leave|leaving|depart|departing)\s*(?:at)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    re.IGNORECASE,
)

_DURATION_DAYS_RE = re.compile(r"\b(\d{1,2})\s*(?:day|days)\b", re.IGNORECASE)

_BAD_TO_TARGETS = {
    "leave",
    "go",
    "come",
    "drive",
    "driving",
    "depart",
    "return",
    "head",
    "start",
    "back",
}

# Stop place capture before common intent phrases so we don't capture:
# "truckey one day trip only", "leave", "come back", etc.
_STOP_AFTER_PLACE = r"(?=\s+(?:one\s+day|same\s+day|day\s+trip|only|and|i\s+want|leave|return|come\s+back)\b|$|[.,!?\n])"

# Handles: "to Truckee from Fremont"
_TO_FROM_RE = re.compile(
    rf"\bto\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}\s+from\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)

# Handles: "from Fremont to Truckee"
_FROM_TO_RE = re.compile(
    rf"\bfrom\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}\s+to\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)

# Handles: "from Fremont"
_FROM_ONLY_RE = re.compile(
    rf"\bfrom\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)

# Handles: "to Truckee"
_TO_ONLY_RE = re.compile(
    rf"\bto\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)

_TRAILING_JUNK = {"only", "trip", "day", "one", "same"}

_INVALID_DEST_SNIPPETS = re.compile(
    r"\b(one\s+day|same\s+day|day\s+trip|only|leave|return|come\s+back)\b",
    re.IGNORECASE,
)

_IN_ONLY_RE = re.compile(
    rf"\bin\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)

_FOR_ONLY_RE = re.compile(
    rf"\bfor\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)

_VISIT_RE = re.compile(
    rf"\bvisit\s+([A-Za-z][A-Za-z\s\.-]{{1,60}}?){_STOP_AFTER_PLACE}",
    re.IGNORECASE,
)


def _hhmm_from_match(hour_str: str, minute_str: Optional[str], ampm: str) -> str:
    hour = int(hour_str)
    minute = int(minute_str) if minute_str else 0
    ampm = ampm.lower()

    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}"


def _is_user(m: Dict[str, Any]) -> bool:
    return (m.get("role") or "").lower() == "user"


def _clean_place(s: str) -> str:
    s = s.strip(" .,-\n\t")
    s = re.sub(r"\s+", " ", s).strip()

    parts = s.split()
    while parts and parts[-1].lower() in _TRAILING_JUNK:
        parts.pop()
    s = " ".join(parts).strip()

    # tiny typo normalization (optional)
    if s.lower() in {"trukkey", "trukee", "trukie", "truckey"}:
        return "Truckee"
    return s


def _is_valid_place_name(name: Optional[str]) -> bool:
    if not name or not isinstance(name, str):
        return False
    n = name.strip()
    if not n:
        return False
    nl = n.lower()
    if nl in _BAD_TO_TARGETS:
        return False
    if _INVALID_DEST_SNIPPETS.search(nl):
        return False
    if len(n.split()) > 6:
        return False
    return True


def _derive_anchors_from_chat(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    # ... (initial variables unchanged)

    origin = None
    destination = None
    duration_days = None
    depart_time_hhmm = None
    return_same_day = None
    travel_mode = None

    for m in history:
        if not _is_user(m):
            continue

        text = (m.get("text") or "").strip()
        if not text:
            continue

        t = " ".join(text.split())  # ← Now t is defined

        # Travel mode
        if re.search(r"\b(by\s+car|drive|driving|road\s*trip)\b", t, re.IGNORECASE):
            travel_mode = "CAR"

        # Duration (explicit)
        md = _DURATION_DAYS_RE.search(t)
        if md:
            try:
                duration_days = int(md.group(1))
            except Exception:
                pass

        # Strong day-trip signals
        if re.search(
            r"\b(same\s+night|same\s+day|day\s+trip|back\s+the\s+same\s+night)\b",
            t,
            re.IGNORECASE,
        ):
            duration_days = 1
            return_same_day = True

        # Depart time
        mt = _TIME_RE.search(t)
        if mt:
            depart_time_hhmm = _hhmm_from_match(mt.group(1), mt.group(2), mt.group(3))

        # ---- Route extraction (priority order) ----
        # 1) "to X from Y"
        tf = _TO_FROM_RE.search(t)
        if tf:
            dest_cand = _clean_place(tf.group(1))
            orig_cand = _clean_place(tf.group(2))
            if _is_valid_place_name(dest_cand):
                destination = dest_cand
            if _is_valid_place_name(orig_cand):
                origin = orig_cand
            continue

        # 2) "from X to Y"
        ft = _FROM_TO_RE.search(t)
        if ft:
            orig_cand = _clean_place(ft.group(1))
            dest_cand = _clean_place(ft.group(2))
            if _is_valid_place_name(orig_cand):
                origin = orig_cand
            if _is_valid_place_name(dest_cand):
                destination = dest_cand
            continue

        # 3) Loose "from X"
        f_only = _FROM_ONLY_RE.search(t)
        if f_only:
            cand = _clean_place(f_only.group(1))
            if _is_valid_place_name(cand):
                origin = cand

        # 4) Loose "to X"
        for m_to in _TO_ONLY_RE.finditer(t):
            cand = _clean_place(m_to.group(1))
            if not _is_valid_place_name(cand):
                continue
            destination = cand
            break

        # ---- NEW: Additional loose destination patterns (lower priority) ----
        # Only apply if we haven't already found a strong destination
        if not destination:
            # "in X"
            i_match = _IN_ONLY_RE.search(t)
            if i_match:
                cand = _clean_place(i_match.group(1))
                if _is_valid_place_name(cand):
                    destination = cand

            # "for X"
            elif _FOR_ONLY_RE.search(t):
                f_match = _FOR_ONLY_RE.search(t)
                cand = _clean_place(f_match.group(1))
                if _is_valid_place_name(cand):
                    destination = cand

            # "visit X"
            elif _VISIT_RE.search(t):
                v_match = _VISIT_RE.search(t)
                cand = _clean_place(v_match.group(1))
                if _is_valid_place_name(cand):
                    destination = cand

    return {
        "origin_name": origin,
        "destination_name": destination,
        "duration_days": duration_days,
        "depart_time_hhmm": depart_time_hhmm,
        "return_same_day": return_same_day,
        "travel_mode": travel_mode,
    }


# -----------------------------
# Existing helpers (unchanged)
# -----------------------------

def to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def _extract_message_text(m: Dict[str, Any]) -> str:
    text = m.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    content = m.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    if isinstance(content, dict):
        for key in ["text", "raw_text", "query", "user_query", "intro_text", "summary", "content"]:
            val = content.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    return ""


def _created_at_key(m: Dict[str, Any]) -> str:
    ts = m.get("created_at")
    if isinstance(ts, datetime):
        return ts.isoformat()
    if isinstance(ts, str):
        return ts
    return ""


class ContextManager:
    """
    Builds a compact context pack:
      - recent_messages (short-term window from db-service)
      - long_term_memories (semantic recall from vector memory via db-service)
      - window_summary (single source of truth)
      - normalized constraints/geoscope/time (pass-through, plus chat-derived fills)
      - api_intents & cache_keys
    """

    def __init__(self):
        self.db = DBServiceClient()

    async def build_context(self, normalized_message: Any) -> Dict[str, Any]:
        nm = to_dict(normalized_message)
        thread_id = nm.get("thread_id")

        # Start with pass-through structured fields from the latest normalized message
        constraints = to_dict(nm.get("constraints", {})) or {}
        geoscope = to_dict(nm.get("geoscope", {})) or {}
        time_block = to_dict(nm.get("time", {})) or {}

        logger.info(
            "CTX: build_context start thread_id=%s nm_message_id=%s nm_keys=%s",
            thread_id,
            nm.get("message_id"),
            list(nm.keys()),
        )

        # ---------------------------------------------
        # 1) Fetch messages: big window for state parse,
        #    short window for LLM context
        # ---------------------------------------------
        recent: List[Dict[str, Any]] = []
        history_for_state: List[Dict[str, Any]] = []

        SHORT_WINDOW = int(getattr(S, "SHORT_WINDOW_MSG_COUNT", 8))
        STATE_WINDOW = max(30, SHORT_WINDOW * 5)

        if thread_id:
            try:
                msgs = await self.db.get_thread_messages(
                    thread_id=thread_id,
                    skip=0,
                    limit=STATE_WINDOW,
                )

                normalized_msgs: List[Dict[str, Any]] = []
                for m in msgs:
                    normalized_msgs.append(
                        {
                            "message_id": m.get("message_id") or m.get("id"),
                            "role": m.get("role"),
                            "text": _extract_message_text(m),
                            "created_at": m.get("created_at"),
                        }
                    )

                # Oldest -> newest for deterministic "latest wins"
                normalized_msgs.sort(key=_created_at_key)

                history_for_state = normalized_msgs
                recent = normalized_msgs[-SHORT_WINDOW:]

            except Exception as e:
                logger.exception("CTX: error fetching thread messages: %s", e)
                recent = []
                history_for_state = []
        else:
            logger.warning("CTX: normalized_message has no thread_id, skipping history fetch")

        # ------------------------------------------------
        # 2) Determine last_user (from history if possible)
        # ------------------------------------------------
        base_list = history_for_state or recent
        user_messages = [m for m in base_list if (m.get("role") == "user")]
        last_user = max(user_messages, key=_created_at_key) if user_messages else None

        # Fallback if DB history empty
        if not last_user:
            def _nm_text(n: Dict[str, Any]) -> str:
                for key in ["text", "raw_text", "query", "user_query"]:
                    val = n.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()

                content = n.get("content")
                if isinstance(content, dict):
                    for key in ["text", "raw_text", "query", "user_query", "content"]:
                        val = content.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()

                if isinstance(content, str) and content.strip():
                    return content.strip()

                return ""

            text = _nm_text(nm)
            mid = nm.get("message_id") or nm.get("id")
            content = nm.get("content")
            if not mid and isinstance(content, dict):
                mid = content.get("message_id") or content.get("id")

            if mid and text:
                last_user = {
                    "message_id": mid,
                    "role": "user",
                    "text": text,
                    "created_at": nm.get("created_at"),
                }

        # ------------------------------------------------------------
        # 2a) NEW: derive anchors from chat + fill missing/invalid
        # ------------------------------------------------------------
        constraints = deepcopy(constraints) if isinstance(constraints, dict) else {}
        geoscope = deepcopy(geoscope) if isinstance(geoscope, dict) else {}
        time_block = deepcopy(time_block) if isinstance(time_block, dict) else {}

        derived = _derive_anchors_from_chat(history_for_state or recent)

        # Fill transport.allowed if empty and we detected CAR
        transport = constraints.get("transport") or {}
        allowed = transport.get("allowed") or []
        if (not allowed) and derived.get("travel_mode") == "CAR":
            transport["allowed"] = ["CAR"]
            constraints["transport"] = transport

        # Fill time.days if missing
        if time_block.get("days") is None and isinstance(derived.get("duration_days"), int):
            time_block["days"] = derived["duration_days"]

        # Optional: depart time
        if derived.get("depart_time_hhmm") and time_block.get("depart_time_local") is None:
            time_block["depart_time_local"] = derived["depart_time_hhmm"]

        # Optional: return same day
        if derived.get("return_same_day") is True and time_block.get("return_same_day") is None:
            time_block["return_same_day"] = True

        # Overwrite invalid geoscope origin/destination (key fix!)
        origin_obj = geoscope.get("origin") if isinstance(geoscope.get("origin"), dict) else {}
        origin_existing = (origin_obj.get("display_name") or origin_obj.get("name")) if isinstance(origin_obj, dict) else None

        dest_obj = geoscope.get("destination") if isinstance(geoscope.get("destination"), dict) else {}
        dest_existing = (dest_obj.get("display_name") or dest_obj.get("name")) if isinstance(dest_obj, dict) else None

        if _is_valid_place_name(derived.get("origin_name")):
            if not _is_valid_place_name(origin_existing):
                geoscope["origin"] = {
                    "name": derived["origin_name"],
                    "display_name": derived["origin_name"],
                }

        if _is_valid_place_name(derived.get("destination_name")):
            if not _is_valid_place_name(dest_existing):
                geoscope["destination"] = {
                    "name": derived["destination_name"],
                    "display_name": derived["destination_name"],
                }

        # If destination == origin, drop destination (avoid nonsense)
        if isinstance(geoscope.get("origin"), dict) and isinstance(geoscope.get("destination"), dict):
            o = (geoscope["origin"].get("display_name") or geoscope["origin"].get("name") or "").strip().lower()
            d = (geoscope["destination"].get("display_name") or geoscope["destination"].get("name") or "").strip().lower()
            if o and d and o == d:
                geoscope["destination"] = None

        # ------------------------------------------------
        # 2b) Window summary AFTER fills (so it's accurate)
        # ------------------------------------------------
        window_summary = self._build_window_summary(constraints, time_block, last_user)

        # ------------------------------------------------
        # 3) Long-term memory (vector DB via db-service)
        # ------------------------------------------------
        long_term_memories: List[Dict[str, Any]] = []
        used_memory_ids: List[str] = []

        try:
            if thread_id and last_user and last_user.get("message_id") and last_user.get("text"):
                await self.db.upsert_memory(
                    thread_id=thread_id,
                    message_id=last_user["message_id"],
                    text=last_user["text"],
                    role="user",
                    extra_meta={"source": "db-service"},
                )
        except Exception as e:
            logger.exception("CTX: VDB upsert failed: %s", e)

        query_text = (last_user.get("text") if last_user else None) or window_summary
        try:
            long_term_memories = await self.db.query_memories(
                thread_id=thread_id,
                query_text=query_text,
                top_k=6,
            )
            for m in long_term_memories:
                meta = m.get("metadata") or {}
                mid = meta.get("message_id") or meta.get("id")
                if mid:
                    m["message_id"] = mid
            used_memory_ids = [m.get("message_id") for m in long_term_memories if m.get("message_id")]
        except Exception as e:
            logger.exception("CTX: VDB query_memories failed: %s", e)
            long_term_memories, used_memory_ids = [], []

        # ------------------------------------
        # 4) API intents and cache keys
        # ------------------------------------
        destination = geoscope.get("destination") or {}
        region = (
            destination.get("region_code")
            or destination.get("name")
            or destination.get("display_name")
        )

        lodging = constraints.get("lodging") or {}
        lodging_types = lodging.get("types") or []
        lodging_type = lodging_types[0] if lodging_types else None
        pet_friendly_required = lodging.get("pet_friendly_required")

        tags = list(
            set(
                (constraints.get("poi_tags", {}).get("must_include") or [])
                + (constraints.get("trip_types") or [])
                + (constraints.get("themes") or [])
            )
        )

        api_intents = [
            {
                "tool": "get_weather",
                "params": {
                    "region": region,
                    "start": time_block.get("start"),
                    "end": time_block.get("end"),
                },
                "caps": {"timeout_s": 6},
            },
            {
                "tool": "search_pois",
                "params": {
                    "region": region,
                    "tags": tags,
                    "pet_friendly": pet_friendly_required,
                    "season_hint": time_block.get("season_hint"),
                },
                "caps": {"limit": 20, "timeout_s": 6},
            },
            {
                "tool": "search_lodging",
                "params": {
                    "region": region,
                    "type": lodging_type,
                    "pet_friendly": pet_friendly_required,
                },
                "caps": {"limit": 3, "timeout_s": 6},
            },
        ]

        cache_keys = {
            "weather": f"weather:{region}:{time_block.get('start')}_{time_block.get('end')}",
            "pois": (
                f"pois:{region}:{'+'.join(sorted(tags))}:"
                f"{time_block.get('season_hint')}:"
                + ("PET" if pet_friendly_required else "ANY")
            ),
            "lodging": (
                f"lodging:{region}:{lodging_type}:"
                + ("PET" if pet_friendly_required else "ANY")
            ),
        }

        context_pack = {
            "type": "context_pack",
            "version": "v1",
            "thread_id": thread_id,
            "message_id": nm.get("message_id"),
            "normalized_ref": {"type": "normalized_message", "version": "v1"},
            "recent_messages": recent,
            "used_window_message_ids": [m["message_id"] for m in recent if m.get("message_id")],
            "window_summary": window_summary,
            "last_user_message": last_user,
            "long_term_memories": long_term_memories,
            "used_memory_ids": used_memory_ids,
            "constraints": constraints,
            "geoscope": geoscope,
            "time": time_block,
            "api_intents": api_intents,
            "cache_keys": cache_keys,
            "applied_fills": {
                "destination_region": region,
                "season": time_block.get("season_hint"),
                "duration_days": time_block.get("days"),
                "memory_hit_count": len(long_term_memories),
                "retrieval_query": (query_text[:160] if query_text else None),
                "derived_from_chat": derived,
            },
        }

        return context_pack

    async def close(self):
        await self.db.close()

    def _build_window_summary(
        self,
        constraints: Dict[str, Any],
        time_block: Dict[str, Any],
        last_user: Dict[str, Any] | None,
    ) -> str:
        summary_parts: List[str] = []

        trip_types_list = constraints.get("trip_types") or []
        trip_types = ", ".join(trip_types_list) if trip_types_list else ""

        raw_diff = constraints.get("difficulty")
        diff = None
        if isinstance(raw_diff, dict):
            diff = raw_diff.get("level")
        elif isinstance(raw_diff, str):
            diff = raw_diff

        raw_budget = constraints.get("budget")
        band = None
        if isinstance(raw_budget, dict):
            band = raw_budget.get("band")
        elif isinstance(raw_budget, str):
            band = raw_budget

        budget_level = constraints.get("budget_level")
        if not band and isinstance(budget_level, str):
            band = budget_level

        transport_allowed = (constraints.get("transport", {}) or {}).get("allowed") or []
        travel_modes = ", ".join(transport_allowed) if transport_allowed else ""

        if trip_types:
            summary_parts.append(trip_types)
        if diff:
            summary_parts.append(f"difficulty {diff}")
        if band:
            summary_parts.append(f"budget {band}")
        if travel_modes:
            summary_parts.append(f"travel by {travel_modes}")

        days = time_block.get("days")
        start = time_block.get("start")
        end = time_block.get("end")
        season_hint = time_block.get("season_hint")

        if isinstance(days, int) and days > 0:
            summary_parts.append(f"{days}-day trip")
        elif start and end:
            summary_parts.append(f"dates {start} \u2192 {end}")
        else:
            summary_parts.append("duration not specified")

        if season_hint:
            summary_parts.append(f"season: {season_hint}")

        window_summary = ("Recent focus: " + "; ".join(summary_parts) + ".") if summary_parts else ""

        if last_user and last_user.get("text"):
            preview = last_user["text"][:120]
            if window_summary:
                window_summary += f" Last user: {preview}..."
            else:
                window_summary = f"Last user: {preview}..."

        return window_summary
