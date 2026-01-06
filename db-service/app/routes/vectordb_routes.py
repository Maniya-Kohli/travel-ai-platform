# app/routes/vdb_routes.py
from fastapi import APIRouter, Query
from typing import Any, Dict, Optional, List
import logging
from app.clients.vector_db_client import VectorDBClient

router = APIRouter(prefix="/vdb", tags=["vdb"])
logger = logging.getLogger(__name__)

vdb = VectorDBClient()

# ---------------------------
# Memories
# ---------------------------

@router.post("/memories")
async def upsert_memory(payload: Dict[str, Any]):
    """
    Expected payload:
    {
      "thread_id": "...",
      "message_id": "...",
      "text": "...",
      "role": "user" | "assistant",
      "embedding": [ ... ],          # REQUIRED (384 floats)
      "extra_meta": { ... }          # optional
    }
    """
    await vdb.upsert_message(
        thread_id=payload["thread_id"],
        message_id=payload["message_id"],
        text=payload["text"],
        role=payload.get("role", "user"),
        embedding=payload["embedding"],                 # ✅ required
        extra_meta=payload.get("extra_meta") or {},
    )
    return {"status": "ok"}


@router.post("/memories/search")
async def search_memories(payload: Dict[str, Any]):
    """
    Expected payload:
    {
      "thread_id": "...",
      "query_embedding": [ ... ],    # REQUIRED (384 floats)
      "top_k": 5
    }
    """
    results = await vdb.query_memories(
        thread_id=payload["thread_id"],
        query_embedding=payload["query_embedding"],     # ✅ required
        top_k=int(payload.get("top_k", 5)),
    )
    return {"count": len(results), "results": results}


@router.get("/memories")
async def list_memories(limit: int = Query(20, ge=1, le=200)):
    docs = vdb.list_all_docs(k=limit)
    return {"count": len(docs), "docs": docs}


@router.post("/delete-all")
async def debug_delete_all():
    deleted = await vdb.delete_all_memories()
    return {"deleted": deleted}


@router.post("/delete-thread")
async def debug_delete_thread(thread_id: str = Query(...)):
    deleted = await vdb.delete_thread_memories(thread_id=thread_id)
    return {"thread_id": thread_id, "deleted": deleted}


# ---------------------------
# Curated Travel Docs
# ---------------------------

@router.post("/travel-docs/upsert-batch")
async def upsert_travel_docs_batch(payload: Dict[str, Any]):
    """
    Expected payload:
    {
      "docs": [
        {"doc_id": "abc", "text": "...", "metadata": {...}, "embedding": [ ... ]},
        ...
      ]
    }
    """
    docs = payload.get("docs") or []
    if not isinstance(docs, list):
        return {"status": "error", "error": "docs must be a list"}

    upserted = await vdb.bulk_upsert_travel_docs(docs=docs)
    return {"status": "ok", "upserted": upserted}


@router.post("/travel-docs/search")
async def search_travel_docs(payload: Dict[str, Any]):
    where: Dict[str, Any] = {}
    if payload.get("region_code"):
        where["region_code"] = payload["region_code"]
    if payload.get("pet_friendly") is not None:
        where["pet_friendly"] = payload["pet_friendly"]
    if payload.get("doc_type"):
        where["type"] = payload["doc_type"]

    results = await vdb.query_travel_docs(
        query_embedding=payload["query_embedding"],
        top_k=int(payload.get("top_k", 8)),
    )
    return {"count": len(results), "results": results}




@router.get("/travel-docs")
async def list_travel_docs(limit: int = Query(20, ge=1, le=200)):
    docs = vdb.list_all_docs(k=limit)
    return {"count": len(docs), "docs": docs}
