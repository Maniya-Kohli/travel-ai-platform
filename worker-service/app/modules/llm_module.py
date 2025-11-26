# app/modules/llm_module.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
import os
import json
import asyncio

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai  # type: ignore
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False
    genai = None  # type: ignore


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
                        "You are an expert travel itinerary planner. "
                        "You ALWAYS respond with a single valid JSON object"
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
        """

        if self._gemini_model is None:
            raise RuntimeError("Gemini model not initialized")

        # Compact inputs for the LLM
        thread_id = context_pack.get("thread_id")
        msg_id = context_pack.get("message_id")
        destination_obj = (context_pack.get("geoscope") or {}).get("destination") or {}
        destination_name = (
            destination_obj.get("display_name")
            or destination_obj.get("name")
            or destination_obj.get("region_code")
            or "your destination"
        )

        # small, focused JSON blobs for the LLM
        llm_input = {
            "context_pack": {
                "thread_id": thread_id,
                "message_id": msg_id,
                "window_summary": context_pack.get("window_summary"),
                "constraints": context_pack.get("constraints"),
                "geoscope": context_pack.get("geoscope"),
                "time": context_pack.get("time"),
            },
            "grounded_context": {
                "pois": grounded_context.get("pois", []),
                "lodging": grounded_context.get("lodging", []),
                "weather": grounded_context.get("weather", {}),
            },
        }

        # Instructions to Gemini – schema + style, but NOT "tabular"
                # Instructions to Gemini – schema + style, but NOT "tabular"
        user_prompt = (
            "You are TravelBot, a friendly but precise trip-planning assistant.\n"
            "Using the JSON below, design a travel itinerary that:\n"
            "  - FOLLOWS THE SCHEMA EXACTLY, and\n"
            "  - RESPECTS WHAT THE TRAVELER ACTUALLY ASKED FOR.\n\n"
            "The traveler’s latest natural-language request is summarized inside "
            "context_pack.window_summary (look for the 'Last user:' portion). "
            "Use that as the primary source of truth for their destination, style, "
            "and preferences. If there is ever a conflict between generic defaults "
            "and what the user said, ALWAYS follow the user.\n\n"
            "Return EXACTLY ONE JSON object with these top-level keys:\n"
            "  type, version, thread_id, message_id, destination, days,\n"
            "  trip_types, difficulty, budget_band, lodging, weather_hint,\n"
            "  window_summary, intro_text, closing_tips, itinerary.\n\n"
            "Details and field requirements:\n"
            "- type must be 'trip_plan'.\n"
            "- version must be 'v1'.\n"
            "- thread_id must equal context_pack.thread_id.\n"
            "- message_id must equal context_pack.message_id.\n"
            "- destination must be a human-readable place name that matches what the user asked for\n"
            "  (e.g. 'Big Sur, California'); do NOT replace it with a generic region.\n"
            "- days is the number of days in the trip (derived from context_pack.time or constraints).\n"
            "- trip_types is a list of short labels like ['CAMPING', 'ROAD_TRIP'].\n"
            "- difficulty is a string like 'EASY', 'MODERATE', or 'HARD'.\n"
            "- budget_band is a code like 'USD_0_500' or 'USD_500_1500'.\n"
            "- lodging is either null or an object {name, type, location, notes} "
            "  with natural, human-readable text.\n"
            "- weather_hint is a short plain-text sentence about the weather or null.\n"
            "- window_summary is a short plain-text recap of the overall trip, written as 1–2\n"
            "  friendly sentences (no bullets, no tables).\n"
            "- intro_text is a 1–2 sentence friendly introduction to the trip, written as if\n"
            "  you’re speaking directly to the traveler.\n"
            "- closing_tips is 1–3 sentences of practical, friendly advice at the end of the trip.\n"
            "- itinerary is an array of day objects. For each day object:\n"
            "    * day: integer day number starting at 1.\n"
            "    * title: friendly title like 'Day 1 – Arrival and Ocean Views'.\n"
            "    * highlights: list of short, human phrases (no markdown),\n"
            "      e.g. 'Sunset at Pfeiffer Beach'.\n"
            "    * activities: list of objects {name, description, tags, estimated_time_hours}.\n"
            "        - name: short label.\n"
            "        - description: 1–3 sentences of natural language, describing\n"
            "          what the traveler will actually do.\n"
            "        - tags: small list of category words like ['HIKE', 'SCENIC'].\n"
            "        - estimated_time_hours: rough numeric estimate (e.g. 2.5).\n\n"
            "PLANNING RULES (VERY IMPORTANT):\n"
            "1) Carefully infer the traveler’s intent from the user text in window_summary.\n"
            "   If the user mentions a specific place (e.g. 'Big Sur'), the trip must be\n"
            "   centered around that specific place, not only the broader state or region.\n"
            "2) Respect constraints in context_pack.constraints (trip_types, difficulty,\n"
            "   budget, duration_days, transport, etc.). Use them to shape the plan.\n"
            "3) Use grounded_context.pois, grounded_context.lodging, and grounded_context.weather\n"
            "   when available. If some data is missing, make reasonable, realistic assumptions.\n"
            "4) Ensure the itinerary across all days feels coherent and not repetitive.\n"
            "5) Every string should sound like a conversational travel assistant speaking to\n"
            "   the traveler (natural, relaxed tone; not a table or API doc).\n\n"
            "OUTPUT FORMAT RULES:\n"
            "- You MUST output ONLY a single JSON object, with no surrounding text.\n"
            "- Inside strings, do NOT use markdown formatting (no **bold**, no numbered lists),\n"
            "  and do NOT output tables.\n"
            "- Write everything as normal, readable sentences, like explaining the plan to a friend.\n\n"
            f"Destination to plan around (from context): {destination_name}.\n"
            "Use any POIs, lodging, and weather info provided. If data is missing,\n"
            "make reasonable assumptions — but the plan must still match what the user asked for.\n\n"
            "Here is the input JSON you must base your answer on:\n"
            f"{json.dumps(llm_input, ensure_ascii=False)}"
        )


        # google-generativeai is sync; run in a thread so our API stays async
        def _run_sync_call() -> Dict[str, Any]:
            response = self._gemini_model.generate_content(
                [user_prompt],
                generation_config={
                    # ask Gemini to return JSON only
                    "response_mime_type": "application/json",
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
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse Gemini JSON: {e} | raw={raw[:400]}")

            # Ensure required top-level fields exist; fill from context if missing
            parsed.setdefault("type", "trip_plan")
            parsed.setdefault("version", "v1")
            parsed.setdefault("thread_id", thread_id)
            parsed.setdefault("message_id", msg_id)
            parsed.setdefault("destination", destination_name)

            return parsed

        trip_plan = await asyncio.to_thread(_run_sync_call)

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
        pois: List[Dict[str, Any]] = grounded_context.get("pois") or []
        lodging: List[Dict[str, Any]] = grounded_context.get("lodging") or []
        weather: Dict[str, Any] = grounded_context.get("weather") or {}

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
            "window_summary": window_summary,
            
            "itinerary": day_plans,
        }

        logger.info("LLMModule._rule_based_plan: finished rule-based trip_plan")
        return trip_plan
