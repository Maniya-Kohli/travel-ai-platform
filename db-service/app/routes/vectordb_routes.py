# app/routes/vdb_routes.py
from fastapi import APIRouter, Query
from typing import Any, Dict
import logging
from app.clients.vector_db_client import VectorDBClient

router = APIRouter(prefix="/vdb", tags=["vdb"])
logger = logging.getLogger(__name__)

# Single shared instance for this process
vdb = VectorDBClient()

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
    logger.info("Upserting memory: %s", payload)

    await vdb.upsert_message(
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
    results = await vdb.query_memories(
        thread_id=thread_id,
        query_text=query,
        top_k=top_k,
    )
    return {"count": len(results), "results": results}

@router.post("/delete-all")
async def debug_delete_all():
    vdb = VectorDBClient()
    deleted = await vdb.delete_all_memories()
    return {"deleted": deleted}

@router.post("/delete-thread")
async def debug_delete_thread(thread_id: str = Query(...)):
    vdb = VectorDBClient()
    deleted = await vdb.delete_thread_memories(thread_id=thread_id)
    return {"thread_id": thread_id, "deleted": deleted}

@router.get("/memories")
async def list_memories(limit: int = Query(20, ge=1, le=200)):
    """
    Return up to `limit` documents from the vector DB
    (for inspection / debugging).
    """

    logger.info('fetching memories')
    docs = vdb.list_all_docs(k=limit)
    return {"count": len(docs), "docs": docs}
