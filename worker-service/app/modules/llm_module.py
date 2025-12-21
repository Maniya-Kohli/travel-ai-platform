# app/modules/llm_module.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
import os
import json
import asyncio
from app.models.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

prompt_manager = PromptManager()

try:
    import google.generativeai as genai  # type: ignore
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False
    genai = None  # type: ignore


def _build_recent_messages_text(
    recent: List[Dict[str, Any]],
    max_messages: int = 4,
) -> str:
    """
    Turn recent_messages into a simple chat transcript string for the LLM.
    We expect each item to already have: {role, text, created_at, message_id}.
    """
    if not recent:
        return ""

    # Take the last N messages (assuming recent is already in time order;
    # if your DB returns newest-first, you can reverse before slicing)
    if len(recent) > max_messages:
        recent = recent[-max_messages:]

    lines: List[str] = []
    for m in recent:
        role = (m.get("role") or "").upper()
        text = (m.get("text") or "").strip()
        if not text:
            continue
        text = text.replace("\n", " ").strip()
        lines.append(f"{role}: {text}")

    return "\n".join(lines)


def _build_long_term_memories_text(
    memories: List[Dict[str, Any]],
    max_memories: int = 4,
) -> str:
    """
    Turn long_term_memories into short bullet points.
    We expect each memory to possibly have text/page_content/content fields.
    """
    if not memories:
        return ""

    bullets: List[str] = []
    for m in memories[:max_memories]:
        text = (
            m.get("text")
            or m.get("page_content")
            or m.get("content")
            or ""
        )
        if not isinstance(text, str):
            continue
        snippet = text.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        bullets.append(f"- {snippet}")

    return "\n".join(bullets)


def _enforce_amenity_notes(
    trip_plan: Dict[str, Any],
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Hard-ish guardrail: if certain amenities are selected in filters, make sure
    every suggested place *mentions* them in human text, even if the LLM forgot.

    For now we enforce this strictly for PARKING:
    - If 'PARKING' is in filters['amenities'], then:
      - trip_plan['lodging'].notes will contain a generic parking note.
      - Every activity.description in itinerary will contain a generic parking note.

    We keep the phrasing generic to avoid hallucinating specific parking details.
    """
    amenities = set(filters.get("amenities") or [])
    if not amenities:
        return trip_plan

    wants_parking = "PARKING" in amenities

    if wants_parking:
        parking_sentence_lodging = (
            "Parking: check ahead for on-site or nearby options, including any fees or time limits."
        )
        parking_sentence_activity = (
            "Parking: check nearby parking options in advance, as availability and cost can vary."
        )

        # ---- Lodging note ----
        lodging = trip_plan.get("lodging")
        if isinstance(lodging, dict):
            notes = lodging.get("notes") or ""
            if "parking" not in notes.lower():
                if notes:
                    notes = notes.rstrip() + " " + parking_sentence_lodging
                else:
                    notes = parking_sentence_lodging
                lodging["notes"] = notes
                trip_plan["lodging"] = lodging

        # ---- Itinerary activities ----
        itinerary = trip_plan.get("itinerary") or []
        if isinstance(itinerary, list):
            for day in itinerary:
                activities = day.get("activities") or []
                if not isinstance(activities, list):
                    continue
                for act in activities:
                    if not isinstance(act, dict):
                        continue
                    desc = act.get("description") or ""
                    if not isinstance(desc, str):
                        desc = str(desc)
                    if "parking" not in desc.lower():
                        if desc:
                            desc = desc.rstrip() + " " + parking_sentence_activity
                        else:
                            desc = parking_sentence_activity
                        act["description"] = desc

    return trip_plan


class LLMModule:
    """
    Trip-planning LLM module.

    - If GEMINI_API_KEY is present and google-generativeai is installed,
      uses Gemini (JSON-mode) to generate a `trip_plan`.
    - Otherwise falls back to the local rule-based planner.

    The JSON shape is:

      {
        "type": "trip_plan",
        "version": "v1",
        "thread_id": "...",
        "message_id": "...",
        "destination": "human readable place",
        "days": 5,
        "trip_types": ["CAMPING", "CITY"],
        "difficulty": "EASY",
        "budget_band": "USD_0_500",
        "lodging": {
          "name": "...",
          "type": "CAMPING" | "HOTEL" | ...,
          "location": "human readable",
          "notes": "short description, human language"
        } | null,
        "weather_hint": "short plain-text summary" | null,
        "window_summary": "short plain-text recap" | null,
        "itinerary": [
          {
            "day": 1,
            "title": "Day 1 in Big Sur – Arrival and Coastal Views",
            "highlights": [
              "Sunset at Pfeiffer Beach",
              "Scenic pullouts along Highway 1"
            ],
            "activities": [
              {
                "name": "Drive the Big Sur coastline",
                "description": "Explain in 1–3 sentences in normal human language.",
                "tags": ["DRIVE", "SCENIC"],
                "estimated_time_hours": 3.5
              },
              ...
            ]
          },
          ...
        ]
      }

    All text fields should be written in natural, human-friendly sentences
    (no markdown tables or numbered list formatting inside the strings).
    """

    def __init__(self) -> None:
        self.use_gemini = False
        self._gemini_model = None

        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL_NAME", "models/gemini-flash-latest")

        if api_key and _HAS_GEMINI:
            try:
                genai.configure(api_key=api_key)
                # We keep the system instructions here so every call shares them
                self._gemini_model = genai.GenerativeModel(
                    model_name,
                    system_instruction=(
                        "You are TravelBot, an expert travel itinerary planner and friendly chat assistant. "
                        "You ALWAYS respond with a single valid JSON object. "
                        "Inside the JSON values, use conversational, natural language as if talking directly to the traveler. "
                        "For summaries, day titles, activity descriptions, and weather hints, write in complete sentences, not lists or fragments."
                    ),
                )
                self.use_gemini = True
                logger.info(
                    "LLMModule initialized with Gemini model=%s", model_name
                )
            except Exception as e:
                logger.exception(
                    "Failed to initialize Gemini, falling back to rule-based planner: %s",
                    e,
                )
        else:
            if not api_key:
                logger.warning(
                    "GEMINI_API_KEY not set – LLMModule in RULE-BASED mode."
                )
            elif not _HAS_GEMINI:
                logger.warning(
                    "google-generativeai not installed – LLMModule in RULE-BASED mode."
                )

        if not self.use_gemini:
            logger.info("LLMModule initialized in RULE-BASED mode (no external LLM).")

    # ------------------------------------------------------------------ public API

    async def generate_plan(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main entrypoint used by TripOrchestrator.

        Tries Gemini first (if available), otherwise falls back to
        the local rule-based planner.
        """
        if self.use_gemini and self._gemini_model is not None:
            try:
                logger.info("LLMModule.generate_plan: using Gemini")
                return await self._call_gemini(grounded_context, context_pack)
            except Exception as e:
                logger.exception(
                    "Gemini call failed, falling back to rule-based planner: %s", e
                )

        logger.info("LLMModule.generate_plan: using RULE-BASED planner")
        return self._rule_based_plan(grounded_context, context_pack)

    # ------------------------------------------------------------------ Gemini path

    async def _call_gemini(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call Gemini in JSON mode to get a structured, but human-readable, trip_plan.
        Now includes:
          - last N recent_messages
          - long_term_memories (vector DB)
          - a normalized `filters` object flattened from constraints/time/lodging
        """

        if self._gemini_model is None:
            raise RuntimeError("Gemini model not initialized")

        # Compact inputs for the LLM
        thread_id = context_pack.get("thread_id")
        msg_id = context_pack.get("message_id")

        geoscope = context_pack.get("geoscope") or {}
        destination_obj = geoscope.get("destination") or {}
        destination_name = (
            destination_obj.get("display_name")
            or destination_obj.get("name")
            or destination_obj.get("region_code")
            or "your destination"
        )

        constraints: Dict[str, Any] = context_pack.get("constraints") or {}
        time_block: Dict[str, Any] = context_pack.get("time") or {}
        transport: Dict[str, Any] = constraints.get("transport") or {}
        lodging_block: Dict[str, Any] = constraints.get("lodging") or {}

        # ----------------- Normalize filters for the LLM -----------------
        difficulty_raw = constraints.get("difficulty")
        if isinstance(difficulty_raw, dict):
            difficulty_norm = difficulty_raw.get("level")
        else:
            difficulty_norm = difficulty_raw

        budget_obj = constraints.get("budget") or {}
        # Prefer budget.band, fallback to budget_level if present
        budget_band = budget_obj.get("band") or constraints.get("budget_level")

        # Merge amenities from both top-level constraints and lodging.amenities_prefer
        amen_top = constraints.get("amenities") or []
        amen_lodging = lodging_block.get("amenities_prefer") or []
        amenities_merged = list({*amen_top, *amen_lodging})

        must_include = (
            (constraints.get("poi_tags") or {}).get("must_include")
            or constraints.get("must_include")
            or []
        )
        must_exclude = (
            (constraints.get("poi_tags") or {}).get("must_exclude")
            or constraints.get("must_exclude")
            or []
        )

        normalized_filters: Dict[str, Any] = {
            "trip_types": constraints.get("trip_types") or [],
            "difficulty": difficulty_norm,
            "budget_band": budget_band,
            "duration_days": (
                constraints.get("duration_days")
                or time_block.get("days")
            ),
            "group_type": constraints.get("group_type"),
            "travel_modes": (
                constraints.get("travel_modes")
                or transport.get("allowed")
                or []
            ),
            "accommodation": lodging_block.get("types") or [],
            "accessibility": constraints.get("accessibility") or [],
            "meal_preferences": (
                constraints.get("diet")
                or constraints.get("meal_preferences")
                or []
            ),
            "must_include": must_include,
            "must_exclude": must_exclude,
            "interest_tags": (
                constraints.get("interest_tags")
                or constraints.get("themes")
                or []
            ),
            "amenities": amenities_merged,
            "events_only": constraints.get("events_only"),
        }

        # Recent conversation & memories from context_pack
        recent_messages: List[Dict[str, Any]] = context_pack.get("recent_messages") or []
        long_term_memories: List[Dict[str, Any]] = context_pack.get("long_term_memories") or []

        # Restrict to last N messages so we don't blow up context
        MAX_RECENT = 4
        if len(recent_messages) > MAX_RECENT:
            recent_messages = recent_messages[-MAX_RECENT:]

        recent_messages_text = _build_recent_messages_text(
            recent_messages,
            max_messages=MAX_RECENT,
        )
        long_term_memories_text = _build_long_term_memories_text(
            long_term_memories,
            max_memories=4,
        )

        retrieved = grounded_context.get("retrieved_data") or {}
        # small, focused JSON blobs for the LLM
        llm_input = {
            "context_pack": {
                "thread_id": thread_id,
                "message_id": msg_id,
                "window_summary": context_pack.get("window_summary"),
                "constraints": constraints,
                "geoscope": geoscope,
                "time": time_block,
                # include history + memories in the structured context
                "recent_messages": recent_messages,
                "long_term_memories": long_term_memories,
                "last_user_message": context_pack.get("last_user_message"),
            },
            "grounded_context": {
            "curated_docs": retrieved.get("curated_docs", []),
            "events": retrieved.get("events", []),
            "pois": retrieved.get("pois", []),
            "rules": retrieved.get("rules", []),
            "lodging": retrieved.get("lodging", []),
            "weather": retrieved.get("weather", None),
            "rag_debug": retrieved.get("rag_debug", {}),
        },
            # Normalized filters for the model to apply strictly
            "filters": normalized_filters,
            # Extra plain-text views that are easy for the LLM to digest
            "recent_messages_text": recent_messages_text,
            "long_term_memories_text": long_term_memories_text,
        }

        base_prompt = await prompt_manager.get_prompt()
        # Let PromptManager's prompt describe what to do with this JSON input
        user_prompt = base_prompt + json.dumps(llm_input, ensure_ascii=False)

        print("LLM INPUT", llm_input)

        # google-generativeai is sync; run in a thread so our API stays async
        def _run_sync_call() -> Dict[str, Any]:
            response = self._gemini_model.generate_content(
                [user_prompt],
                generation_config={
                    # ask Gemini to return JSON only
                    "response_mime_type": "application/json",
                    "temperature": 0.4,
                },
            )

            # In JSON mode, response.text should already be pure JSON
            raw = getattr(response, "text", None)
            if not raw:
                # safety: try to dig into parts if text is empty
                try:
                    parts = response.candidates[0].content.parts
                    raw = "".join(p.text for p in parts if hasattr(p, "text"))
                except Exception:
                    raise RuntimeError("Gemini response had no text content")

            try:
                parsed = json.loads(raw)
                print("llm response", response)

                trip_plan: Dict[str, Any]

                # Case 1: wrapper object { "reply": { ...trip_plan... } }
                if isinstance(parsed, dict) and "reply" in parsed:
                    trip_plan = parsed["reply"]

                # Case 2: bare trip_plan object { "type": "trip_plan", ... }
                elif isinstance(parsed, dict) and parsed.get("type") == "trip_plan":
                    trip_plan = parsed

                else:
                    raise RuntimeError(
                        "LLM response did not contain a valid trip_plan "
                        "(no 'reply' and no top-level type=='trip_plan')"
                    )

            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Failed to parse Gemini JSON: {e} | raw={raw[:400]}"
                )

            # Ensure required top-level fields exist; fill from context if missing
            trip_plan.setdefault("type", "trip_plan")
            trip_plan.setdefault("version", "v1")
            trip_plan.setdefault("thread_id", thread_id)
            trip_plan.setdefault("message_id", msg_id)
            trip_plan.setdefault("destination", destination_name)

            return trip_plan

        # actually run the sync call in a thread
        trip_plan = await asyncio.to_thread(_run_sync_call)

        # 🔒 Enforce amenity-related notes (e.g., PARKING) on every suggested place
        trip_plan = _enforce_amenity_notes(trip_plan, normalized_filters)

        logger.info("LLMModule._call_gemini: received trip_plan from Gemini")
        return trip_plan

    # ------------------------------------------------------------------ Rule-based fallback (old logic)

    def _rule_based_plan(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Simple local planner that returns the same JSON shape as Gemini,
        but with less detail. Text is also in human-readable language.
        """
        constraints: Dict[str, Any] = context_pack.get("constraints", {}) or {}
        time_block: Dict[str, Any] = context_pack.get("time", {}) or {}
        geoscope: Dict[str, Any] = context_pack.get("geoscope", {}) or {}

        destination_obj = geoscope.get("destination") or {}
        destination_name = (
            destination_obj.get("display_name")
            or destination_obj.get("name")
            or destination_obj.get("region_code")
            or "your destination"
        )

        # how many days?
        days: int = (
            time_block.get("days")
            or constraints.get("duration_days")
            or 3  # default
        )

        trip_types = constraints.get("trip_types") or []
        difficulty = (
            (constraints.get("difficulty") or {}).get("level")
            or constraints.get("difficulty")
            or "EASY"
        )
        budget_band = (
            (constraints.get("budget") or {}).get("band")
            or constraints.get("budget_level")
            or "USD_0_500"
        )

        # RAG outputs
        retrieved = grounded_context.get("retrieved_data") or {}
        pois: List[Dict[str, Any]] = retrieved.get("pois") or []
        lodging: List[Dict[str, Any]] = retrieved.get("lodging") or []
        weather = retrieved.get("weather") or {}


        logger.info(
            "LLMModule._rule_based_plan: destination=%s days=%s pois=%d lodging=%d",
            destination_name,
            days,
            len(pois),
            len(lodging),
        )

        # Simple heuristic: up to 3 POIs per day
        max_pois_per_day = 3
        pois_for_plan = pois[: days * max_pois_per_day]

        day_plans: List[Dict[str, Any]] = []

        for day_idx in range(days):
            day_number = day_idx + 1
            start = day_idx * max_pois_per_day
            end = start + max_pois_per_day
            day_pois = pois_for_plan[start:end]

            activities = []
            for poi in day_pois:
                name = poi.get("name") or poi.get("title") or "Unknown spot"
                desc = (
                    poi.get("description")
                    or poi.get("summary")
                    or f"Spend some relaxed time exploring {name}."
                )
                activities.append(
                    {
                        "name": name,
                        "description": desc,
                        "tags": poi.get("tags") or poi.get("categories") or [],
                        "estimated_time_hours": 2,
                    }
                )

            title = f"Day {day_number} in {destination_name}"
            if day_number == 1:
                title += " – Arrival and first impressions"
            elif day_number == days:
                title += " – Farewell and final stops"

            day_plans.append(
                {
                    "day": day_number,
                    "title": title,
                    "highlights": [a["name"] for a in activities]
                    or [f"Explore {destination_name} at your own pace"],
                    "activities": activities,
                }
            )

        # Lodging suggestion (very simple for now)
        primary_lodging: Optional[Dict[str, Any]] = lodging[0] if lodging else None
        lodging_summary = None
        if primary_lodging:
            lodging_summary = {
                "name": primary_lodging.get("name") or "Suggested lodging",
                "type": primary_lodging.get("type"),
                "location": primary_lodging.get("location")
                or primary_lodging.get("address"),
                "notes": primary_lodging.get("notes")
                or primary_lodging.get("description")
                or f"A practical place to stay in or near {destination_name}.",
            }

        # Weather hint
        weather_hint = None
        if isinstance(weather, dict):
            weather_hint = (
                weather.get("summary")
                or weather.get("forecast_summary")
                or None
            )

        window_summary = context_pack.get("window_summary")

        trip_plan: Dict[str, Any] = {
            "window_summary": window_summary,
            "type": "trip_plan",
            "version": "v1",
            "thread_id": context_pack.get("thread_id"),
            "message_id": context_pack.get("message_id"),
            "destination": destination_name,
            "days": days,
            "trip_types": trip_types,
            "difficulty": difficulty,
            "budget_band": budget_band,
            "lodging": lodging_summary,
            "weather_hint": weather_hint,
            "itinerary": day_plans,
        }

        logger.info("LLMModule._rule_based_plan: finished rule-based trip_plan")
        return trip_plan
