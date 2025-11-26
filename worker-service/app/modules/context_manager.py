# app/modules/context_manager.py
from __future__ import annotations
from typing import Any, Dict, List

from app.config import get_settings
from app.clients.db_service_client import DBServiceClient
import logging

logger = logging.getLogger(__name__)
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
      - long_term_memories (semantic recall from vector memory via db-service)
      - window_summary (light heuristic, but no fake defaults)
      - normalized constraints/geoscope/time (pass-through)
      - api_intents & cache_keys (simple fetch plan)
    """

    def __init__(self):
        self.db = DBServiceClient()   # proxies vector DB ops too

    async def build_context(self, normalized_message: Any) -> Dict[str, Any]:
        # Safely convert top-level (could be model or dict)
        nm = to_dict(normalized_message)
        thread_id = nm.get("thread_id")
        constraints = to_dict(nm.get("constraints", {}))
        geoscope = to_dict(nm.get("geoscope", {}))
        time_block = to_dict(nm.get("time", {}))

        logger.info(
            "CTX: build_context start thread_id=%s nm_message_id=%s nm_keys=%s",
            thread_id,
            nm.get("message_id"),
            list(nm.keys()),
        )

        # ---- 1) Short-term memory: last N messages from db-service ----
        logger.info("CTX: creating short-term memories...")
        recent: List[Dict[str, Any]] = []

        if thread_id:
            try:
                msgs = await self.db.get_thread_messages(
                    thread_id=thread_id,
                    skip=0,
                    limit=S.SHORT_WINDOW_MSG_COUNT,
                )
                logger.info(
                    "CTX: got %d messages from db-service for thread_id=%s",
                    len(msgs),
                    thread_id,
                )
                for m in msgs:
                    rec = {
                        "message_id": m.get("message_id") or m.get("id"),
                        "role": m.get("role"),
                        "text": (
                            m.get("text")
                            if m.get("text") is not None
                            else m.get("content")
                        ),
                        "created_at": m.get("created_at"),
                    }
                    logger.debug("CTX: recent message=%s", rec)
                    recent.append(rec)
            except Exception as e:
                logger.exception("CTX: error fetching thread messages: %s", e)
                recent = []
        else:
            logger.warning(
                "CTX: normalized_message has no thread_id, skipping recent history"
            )

        # ---- 2) Determine last_user (with fallback for first message) ----
        logger.info("CTX: building window summary & last_user...")

        last_user = next(
            (m for m in reversed(recent) if m.get("role") == "user"),
            None,
        )

        # Fallback for first message / empty history:
        if last_user is None:
            logger.info(
                "CTX: no last_user from recent; trying to synthesize from normalized_message"
            )

            def _nm_text(n: Dict[str, Any]) -> str:
                # 1) Top-level candidates
                for key in ["text", "raw_text", "query", "user_query"]:
                    val = n.get(key)
                    if isinstance(val, str) and val.strip():
                        return val

                # 2) Look inside content if it's a dict
                content = n.get("content")
                if isinstance(content, dict):
                    for key in ["text", "raw_text", "query", "user_query", "content"]:
                        val = content.get(key)
                        if isinstance(val, str) and val.strip():
                            return val

                # 3) If content itself is a string
                if isinstance(content, str) and content.strip():
                    return content

                return ""

            text = _nm_text(nm)

            # Message id might also be nested in content
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
                logger.info(
                    "CTX: synthesized last_user from normalized_message: %s",
                    last_user,
                )
            else:
                logger.info(
                    "CTX: no last_user found in recent and could not synthesize "
                    "(mid=%s, text_present=%s)",
                    mid,
                    bool(text),
                )

        logger.info("CTX: final last_user for thread_id=%s => %s", thread_id, last_user)

        # ---- Window summary (no fake defaults) ----
        summary_parts: List[str] = []

        # difficulty can be either {"level": "..."} or plain string
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

        transport_allowed = (
            constraints.get("transport", {}).get("allowed") or []
        )
        travel_modes = ", ".join(transport_allowed) if transport_allowed else ""

        trip_types_list = constraints.get("trip_types") or []
        trip_types = ", ".join(trip_types_list) if trip_types_list else ""

        if trip_types:
            summary_parts.append(trip_types)
        if diff:
            summary_parts.append(f"difficulty {diff}")
        if band:
            summary_parts.append(f"budget {band}")
        if travel_modes:
            summary_parts.append(f"travel by {travel_modes}")

        if summary_parts:
            window_summary = "Recent focus: " + "; ".join(summary_parts) + "."
        else:
            window_summary = ""

        if last_user and last_user.get("text"):
            # Append last user text if we have it
            preview = last_user["text"][:120]
            if window_summary:
                window_summary += f" Last user: {preview}..."
            else:
                window_summary = f"Last user: {preview}..."

        # ---- 3) Long-term memory via db-service (vector DB proxied there) ----
        logger.info("CTX: creating long-term memories...")
        long_term_memories: List[Dict[str, Any]] = []
        used_memory_ids: List[str] = []

        # 3a. Upsert last user message into vector DB via db-service
        try:
            if (
                thread_id
                and last_user
                and last_user.get("message_id")
                and last_user.get("text")
            ):
                logger.info(
                    "CTX: calling db.upsert_memory thread_id=%s message_id=%s text_preview=%s",
                    thread_id,
                    last_user["message_id"],
                    last_user["text"][:80] if last_user.get("text") else None,
                )
                await self.db.upsert_memory(
                    thread_id=thread_id,
                    message_id=last_user["message_id"],
                    text=last_user["text"],
                    role="user",
                    extra_meta={"source": "db-service"},
                )
            else:
                logger.warning(
                    "CTX: NOT upserting memory. Reasons -> thread_id=%s, has_last_user=%s, "
                    "has_message_id=%s, has_text=%s",
                    thread_id,
                    bool(last_user),
                    bool(last_user and last_user.get("message_id")),
                    bool(last_user and last_user.get("text")),
                )
        except Exception as e:
            logger.exception("CTX: VDB upsert failed: %s", e)

        # 3b. Query memories via db-service
        query_text = (last_user.get("text") if last_user else None) or window_summary
        try:
            long_term_memories = await self.db.query_memories(
                thread_id=thread_id,
                query_text=query_text,
                top_k=6,
            )
            logger.info(
                "CTX: retrieved %d long_term_memories for thread_id=%s",
                len(long_term_memories),
                thread_id,
            )
            for m in long_term_memories:
                meta = m.get("metadata") or {}
                mid = meta.get("message_id") or meta.get("id")
                if mid:
                    m["message_id"] = mid
            used_memory_ids = [
                m.get("message_id")
                for m in long_term_memories
                if m.get("message_id")
            ]
        except Exception as e:
            logger.exception("CTX: VDB query_memories failed: %s", e)
            long_term_memories, used_memory_ids = [], []

        # ---- 4) API intents and cache keys ----
        # Internal defaults are still OK for tools; they are not user-facing.
        region = (geoscope.get("destination") or {}).get(
            "region_code", S.DEFAULT_REGION_CODE
        )
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
                    "pet_friendly": constraints.get("lodging", {}).get(
                        "pet_friendly_required", False
                    ),
                    "season_hint": time_block.get("season_hint"),
                },
                "caps": {"limit": 20, "timeout_s": 6},
            },
            {
                "tool": "search_lodging",
                "params": {
                    "region": region,
                    "type": (
                        constraints.get("lodging", {}).get("types")
                        or ["CAMPING"]
                    )[0],
                    "pet_friendly": constraints.get("lodging", {}).get(
                        "pet_friendly_required", False
                    ),
                },
                "caps": {"limit": 3, "timeout_s": 6},
            },
        ]

        cache_keys = {
            "weather": f"weather:{region}:{time_block.get('start')}_{time_block.get('end')}",
            "pois": (
                f"pois:{region}:{'+'.join(sorted(tags))}:"
                f"{time_block.get('season_hint')}:"
                + (
                    "PET"
                    if constraints.get("lodging", {}).get(
                        "pet_friendly_required"
                    )
                    else "ANY"
                )
            ),
            "lodging": (
                f"lodging:{region}:"
                f"{(constraints.get('lodging', {}).get('types') or ['CAMPING'])[0]}:"
                + (
                    "PET"
                    if constraints.get("lodging", {}).get(
                        "pet_friendly_required"
                    )
                    else "ANY"
                )
            ),
        }

        context_pack = {
            "type": "context_pack",
            "version": "v1",
            "thread_id": thread_id,
            "message_id": nm.get("message_id"),
            "normalized_ref": {
                "type": "normalized_message",
                "version": "v1",
            },
            "recent_messages": recent,
            "used_window_message_ids": [
                m["message_id"] for m in recent if m.get("message_id")
            ],
            "window_summary": window_summary,
            "last_user": last_user,  # 👈 expose explicitly for the LLM layer
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
            },
        }
        return context_pack

    async def close(self):
        await self.db.close()
