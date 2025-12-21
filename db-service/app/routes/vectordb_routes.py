# app/routes/vdb_routes.py
from fastapi import APIRouter, Query
from typing import Any, Dict, Optional
import logging
from app.clients.vector_db_client import VectorDBClient

router = APIRouter(prefix="/vdb", tags=["vdb"])
logger = logging.getLogger(__name__)

# Two shared instances (two Chroma collections)
vdb_memories = VectorDBClient(collection_name="memories")
vdb_travel_docs = VectorDBClient(collection_name="travel_docs")


# ---------------------------
# Memories 
# ---------------------------

@router.post("/memories")
async def upsert_memory(payload: Dict[str, Any]):
    """
    Upsert one memory (message) into the vector DB.
    Expected payload:
    {
      "thread_id": "...",
      "message_id": "...",
      "text": "...",
      "role": "user" | "assistant",
      "extra_meta": { ... }   # optional
    }
    """
    logger.info(
        "Upserting memory: thread_id=%s message_id=%s",
        payload.get("thread_id"),
        payload.get("message_id"),
    )

    await vdb_memories.upsert_message(
        thread_id=payload["thread_id"],
        message_id=payload["message_id"],
        text=payload["text"],
        role=payload.get("role", "user"),
        extra_meta=payload.get("extra_meta") or {},
    )
    return {"status": "ok"}


@router.get("/memories/search")
async def search_memories(
    thread_id: str = Query(...),
    query: str = Query(...),
    top_k: int = 5,
):
    """
    Search memories for a given thread_id with a query string.
    Used by the worker ContextManager.
    """
    results = await vdb_memories.query_memories(
        thread_id=thread_id,
        query_text=query,
        top_k=top_k,
    )
    return {"count": len(results), "results": results}


@router.get("/memories")
async def list_memories(limit: int = Query(20, ge=1, le=200)):
    """Return up to `limit` memory docs (debug)."""
    docs = vdb_memories.list_all_docs(k=limit)
    return {"count": len(docs), "docs": docs}


@router.post("/delete-all")
async def debug_delete_all():
    # deletes only the memories collection (keeps behavior the same)
    deleted = await vdb_memories.delete_all_memories()
    return {"deleted": deleted}


@router.post("/delete-thread")
async def debug_delete_thread(thread_id: str = Query(...)):
    deleted = await vdb_memories.delete_thread_memories(thread_id=thread_id)
    return {"thread_id": thread_id, "deleted": deleted}


# ---------------------------
# Curated Travel Docs 
# ---------------------------

@router.post("/travel-docs/upsert-batch")
async def upsert_travel_docs_batch(payload: Dict[str, Any]):
    """
    Bulk upsert curated travel docs into the `travel_docs` collection.

    Expected payload:
    {
      "docs": [
        {"doc_id": "abc", "text": "...", "metadata": {...}},
        ...
      ]
    }
    """
    docs = payload.get("docs") or []
    if not isinstance(docs, list):
        return {"status": "error", "error": "docs must be a list"}

    upserted = await vdb_travel_docs.bulk_upsert_travel_docs(docs=docs)
    return {"status": "ok", "upserted": upserted}


@router.get("/travel-docs/search")
async def search_travel_docs(
    query: str = Query(...),
    top_k: int = 8,
    region_code: Optional[str] = None,
    pet_friendly: Optional[bool] = None,
    doc_type: Optional[str] = None,
):
    """
    Query curated travel docs.
    Keep filters simple (exact matches) so Chroma metadata filtering works well.
    """
    where: Dict[str, Any] = {}
    if region_code:
        where["region_code"] = region_code
    if pet_friendly is not None:
        where["pet_friendly"] = pet_friendly
    if doc_type:
        where["type"] = doc_type

    results = await vdb_travel_docs.query_travel_docs(
        query_text=query,
        top_k=top_k,
        where=where or None,
    )
    return {"count": len(results), "results": results}


@router.get("/travel-docs")
async def list_travel_docs(limit: int = Query(20, ge=1, le=200)):
    """Return up to `limit` travel docs (debug)."""
    docs = vdb_travel_docs.list_all_docs(k=limit)
    return {"count": len(docs), "docs": docs}
