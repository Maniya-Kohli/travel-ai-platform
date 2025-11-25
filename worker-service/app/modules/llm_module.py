# app/modules/llm_module.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class LLMModule:
    """
    For now this is a *rule-based* trip planner, i.e. NOT calling any paid LLM.
    It consumes:
      - context_pack: constraints, geoscope, time, memories...
      - grounded_context: data_retriever output (POIs, lodging, weather...)
    and returns a JSON-serializable trip_plan dict.

    Later you can swap the internals of generate_plan() to call a real LLM
    (OpenAI, HuggingFace, Ollama, etc.) without changing the orchestrator.
    """

    def __init__(self) -> None:
        # If you later want to switch to a real LLM, you can add config here.
        logger.info("LLMModule initialized in RULE-BASED mode (no external LLM calls).")

    async def generate_plan(
        self,
        grounded_context: Dict[str, Any],
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build a simple but structured trip plan using only Python logic
        (no external LLM, so it's completely free).

        Returns a dict that TripOrchestrator will store in the messages table.
        """

        logger.info("LLMModule.generate_plan: start building rule-based trip plan")

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
        difficulty = (constraints.get("difficulty") or {}).get("level") or constraints.get("difficulty") or "EASY"
        budget_band = (constraints.get("budget") or {}).get("band") or constraints.get("budget_level") or "USD_0_500"

        # RAG outputs
        pois: List[Dict[str, Any]] = (grounded_context.get("pois") or [])
        lodging: List[Dict[str, Any]] = (grounded_context.get("lodging") or [])
        weather: Dict[str, Any] = (grounded_context.get("weather") or {})

        logger.info(
            "LLMModule.generate_plan: destination=%s days=%s pois=%d lodging=%d",
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
                activities.append(
                    {
                        "name": poi.get("name") or poi.get("title") or "Unknown spot",
                        "description": poi.get("description") or poi.get("summary"),
                        "tags": poi.get("tags") or poi.get("categories") or [],
                        "estimated_time_hours": 2,
                    }
                )

            title = f"Day {day_number} in {destination_name}"
            if day_number == 1:
                title += " – Arrival & Scenic Intro"
            elif day_number == days:
                title += " – Wrap-up & Relax"

            day_plans.append(
                {
                    "day": day_number,
                    "title": title,
                    "highlights": [a["name"] for a in activities] or [f"Explore {destination_name}"],
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
                "location": primary_lodging.get("location") or primary_lodging.get("address"),
                "notes": primary_lodging.get("notes") or primary_lodging.get("description"),
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

        logger.info("LLMModule.generate_plan: finished rule-based trip_plan")
        return trip_plan


    # ------------------------------------------------------------------
    # OPTIONAL: when you want a *real* LLM later, you can replace
    # generate_plan() with a call to OpenAI / HF / local Ollama here.
    #
    # Example skeleton (NOT used right now):
    #
    # async def _call_real_llm(self, grounded_context: Dict[str, Any], context_pack: Dict[str, Any]) -> Dict[str, Any]:
    #     from openai import AsyncOpenAI
    #     import os
    #
    #     client = AsyncOpenAI()
    #     model = os.getenv("OPENAI_LLM_MODEL", "gpt-4.1-mini")
    #
    #     system_msg = "You are a travel-planning assistant..."
    #     user_msg = f"Here is context_pack: {json.dumps(context_pack)}\n" \
    #                f"And grounded_context: {json.dumps(grounded_context)}\n" \
    #                "Return a JSON trip plan with fields: ... "
    #
    #     resp = await client.chat.completions.create(
    #         model=model,
    #         messages=[
    #             {"role": "system", "content": system_msg},
    #             {"role": "user", "content": user_msg},
    #         ],
    #         response_format={"type": "json_object"},
    #     )
    #
    #     content = resp.choices[0].message.content
    #     return json.loads(content)
    # ------------------------------------------------------------------
