# app/modules/data_retriever.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging

from app.clients.db_service_client import DBServiceClient

logger = logging.getLogger(__name__)


class DataRetriever:
    """
    Curated RAG only (Phase 1):
    - Pulls relevant docs from db-service's Chroma collection: travel_docs
    - No external APIs (no Open-Meteo, no Wikipedia)
    - Returns a grounded_context object with retrieved_data populated
      so LLMModule can ground answers.

    Output shape:
      grounded_context["retrieved_data"] = {
        "curated_docs": [ {text, metadata, score}, ... ],
        "events": [...],
        "pois": [...],
        "rules": [...],
        "lodging": [],
        "weather": None,
        "rag_debug": {...}
      }
    """

    def __init__(self) -> None:
        logger.info("DR: DataRetriever initialized (curated RAG only)")
        self.db_client = DBServiceClient()

    async def retrieve(self, context_pack: Dict[str, Any]) -> Dict[str, Any]:
        thread_id = context_pack.get("thread_id")

        geoscope: Dict[str, Any] = context_pack.get("geoscope", {}) or {}
        destination: Dict[str, Any] = geoscope.get("destination", {}) or {}

        constraints: Dict[str, Any] = context_pack.get("constraints", {}) or {}
        lodging_constraints = constraints.get("lodging", {}) or {}
        pet_required = lodging_constraints.get("pet_friendly_required", None)

        trip_types = constraints.get("trip_types") or []
        themes = constraints.get("themes") or []
        poi_tags = (constraints.get("poi_tags") or {}).get("must_include") or []

        last_user_text = (context_pack.get("last_user_message") or {}).get("text", "") or ""
        window_summary = context_pack.get("window_summary", "") or ""

        # If destination is missing, we still retrieve generally for "California"
        place_name = (
            destination.get("name")
            or destination.get("primary_city")
            or destination.get("region_label")
            or destination.get("region_code")
            or "California"
        )
        region_code = destination.get("region_code")  # can be None

        # Build a high-signal retrieval query.
        # Keep it simple: user's message + summary + place + tags.
        query_text = " ".join(
            x for x in [
                last_user_text,
                window_summary,
                place_name,
                " ".join(trip_types) if trip_types else "",
                " ".join(themes) if themes else "",
                " ".join(poi_tags) if poi_tags else "",
                "pet friendly" if pet_required else "",
            ]
            if x
        ).strip()

        logger.info("DR: curated RAG start thread_id=%s", thread_id)
        logger.info("DR: curated RAG query_text=%s", query_text[:200])
        logger.info("DR: curated RAG filters region_code=%s pet_required=%s", region_code, pet_required)

        try:
            curated_docs: List[Dict[str, Any]] = await self.db_client.query_travel_docs(
                query_text=query_text,
                top_k=12,
                region_code=region_code,
                pet_friendly=True if pet_required else None,  # apply only if required
                doc_type=None,
            )
        except Exception:
            logger.exception("DR: curated travel_docs query failed")
            curated_docs = []

        # Optional: split docs by type so prompt can consume more easily
        def _dtype(d: Dict[str, Any]) -> str:
            meta = d.get("metadata") or {}
            return str(meta.get("type") or "").upper()

        events = [d for d in curated_docs if _dtype(d) == "EVENT"]
        rules = [d for d in curated_docs if _dtype(d) == "RULE"]

        # "POIs" bucket: anything that is not RULE (events + hikes + attractions etc.)
        pois = [d for d in curated_docs if _dtype(d) != "RULE"]

        retrieved_data: Dict[str, Any] = {
            "weather": None,          # not used in curated phase
            "lodging": [],            # not used in curated phase (yet)
            "curated_docs": curated_docs,
            "events": events,
            "pois": pois,
            "rules": rules,
            "rag_debug": {
                "query_text": query_text,
                "place_name": place_name,
                "region_code": region_code,
                "pet_required": pet_required,
                "retrieved_count": len(curated_docs),
            },
        }

        logger.info(
            "DR: curated RAG done thread_id=%s retrieved_count=%d",
            thread_id,
            len(curated_docs),
        )

        # Keep your current contract: return a dict that includes context_pack fields
        # and adds retrieved_data.
        grounded_context = {
            **context_pack,
            "retrieved_data": retrieved_data,
        }
        return grounded_context

    async def close(self) -> None:
        try:
            await self.db_client.close()
        except Exception:
            pass
