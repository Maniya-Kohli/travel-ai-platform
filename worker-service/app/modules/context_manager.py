# app/modules/context_manager.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.clients.db_service_client import DBServiceClient
from app.clients.vector_db_client import VectorDBClient  # <- your LangChain-based client (Chroma + embeddings)

S = get_settings()

def to_dict(obj):
        # Converts Pydantic models or other objects to dicts
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        return obj

class ContextManager:
    """
    Builds a compact context pack:
      - recent_messages (short-term window from db-service)
      - long_term_memories (semantic recall from vector memory via LangChain)
      - window_summary (light heuristic)
      - normalized constraints/geoscope/time (pass-through)
      - api_intents & cache_keys (simple fetch plan)
    """

    def __init__(self):
        self.db = DBServiceClient()
        self.vdb = VectorDBClient()   # LangChain embeddings + Chroma (local) in v0
        self.vdb.list_all_docs()
    
    async def build_context(self, normalized_message: Any) -> Dict[str, Any]:
        # Safely convert top-level (could be model or dict)
        nm = to_dict(normalized_message)
        thread_id = nm.get("thread_id")
        constraints = to_dict(nm.get("constraints", {}))
        geoscope = to_dict(nm.get("geoscope", {}))
        time_block = to_dict(nm.get("time", {}))

        # ---- 1) Short-term memory: last N messages from db-service ----
        recent: List[Dict[str, Any]] = []
        if thread_id:
            try:
                msgs = await self.db.get_thread_messages(
                    thread_id=thread_id, skip=0, limit=S.SHORT_WINDOW_MSG_COUNT
                )
                for m in msgs:
                    recent.append({
                        "message_id": m.get("message_id") or m.get("id"),
                        "role": m.get("role"),
                        "text": m.get("text") if m.get("text") is not None else m.get("content"),
                        "created_at": m.get("created_at"),
                    })
            except Exception:
                recent = []

        # ---- 2) Window summary (flexible dict access) ----
        last_user = next((m for m in reversed(recent) if m.get("role") == "user"), None)
        diff = (constraints.get("difficulty") or {}).get("level", "EASY")
        band = (constraints.get("budget") or {}).get("band", "USD_0_500")
        travel_modes = ", ".join(constraints.get("transport", {}).get("allowed", []) or ["CAR"])
        trip_types = ", ".join(constraints.get("trip_types", []) or ["CAMPING"])
        window_summary = (
            f"Recent focus: {trip_types}; difficulty {diff}; budget {band}; travel by {travel_modes}."
            + (f" Last user: {last_user['text'][:120]}..." if last_user and last_user.get("text") else "")
        )

        # ---- 3) Long-term memory (as before) ----
        long_term_memories: List[Dict[str, Any]] = []
        used_memory_ids: List[str] = []

        try:
            if thread_id and last_user and last_user.get("message_id") and last_user.get("text"):
                await self.vdb.upsert_message(
                    thread_id=thread_id,
                    message_id=last_user["message_id"],
                    text=last_user["text"],
                    role="user",
                    extra_meta={"source": "db-service"}
                )
        except Exception:
            pass

        query_text = (last_user.get("text") if last_user else None) or window_summary
        try:
            long_term_memories = await self.vdb.query_memories(
                thread_id=thread_id,
                query_text=query_text,
                top_k=6
            )
            for m in long_term_memories:
                meta = m.get("metadata") or {}
                mid = meta.get("message_id") or meta.get("id")
                if mid:
                    m["message_id"] = mid
            used_memory_ids = [m.get("message_id") for m in long_term_memories if m.get("message_id")]
        except Exception:
            long_term_memories, used_memory_ids = [], []

        # ---- 4) API intents and cache keys ----
        region = (geoscope.get("destination") or {}).get("region_code", S.DEFAULT_REGION_CODE)
        tags = list(set(
            (constraints.get("poi_tags", {}).get("must_include") or [])
            + (constraints.get("trip_types") or [])
            + (constraints.get("themes") or [])
        ))

        api_intents = [
            { "tool": "get_weather",
            "params": { "region": region, "start": time_block.get("start"), "end": time_block.get("end") },
            "caps": { "timeout_s": 6 } },
            { "tool": "search_pois",
            "params": { "region": region, "tags": tags,
                        "pet_friendly": constraints.get("lodging", {}).get("pet_friendly_required", False),
                        "season_hint": time_block.get("season_hint") },
            "caps": { "limit": 20, "timeout_s": 6 } },
            { "tool": "search_lodging",
            "params": { "region": region,
                        "type": (constraints.get("lodging", {}).get("types") or ["CAMPING"])[0],
                        "pet_friendly": constraints.get("lodging", {}).get("pet_friendly_required", False) },
            "caps": { "limit": 3, "timeout_s": 6 } },
        ]

        cache_keys = {
            "weather": f"weather:{region}:{time_block.get('start')}_{time_block.get('end')}",
            "pois":    f"pois:{region}:{'+'.join(sorted(tags))}:{time_block.get('season_hint')}:" +
                    ("PET" if constraints.get('lodging', {}).get('pet_friendly_required') else "ANY"),
            "lodging": f"lodging:{region}:{(constraints.get('lodging', {}).get('types') or ['CAMPING'])[0]}:" +
                    ("PET" if constraints.get('lodging', {}).get('pet_friendly_required') else 'ANY'),
        }

        context_pack = {
            "type": "context_pack",
            "version": "v1",
            "thread_id": thread_id,
            "message_id": nm.get("message_id"),
            "normalized_ref": { "type": "normalized_message", "version": "v1" },
            "recent_messages": recent,
            "used_window_message_ids": [m["message_id"] for m in recent if m.get("message_id")],
            "window_summary": window_summary,
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
            }
        }
        return context_pack



    async def close(self):
        await self.db.close()
        # VectorDBClient (Chroma) has no async close; nothing to do here.
