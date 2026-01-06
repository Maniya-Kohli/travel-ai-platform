# from fastapi import APIRouter
# from typing import Any, Dict
# import json
# import logging
# from pathlib import Path
# from app.clients.vector_db_client import VectorDBClient

# router = APIRouter(prefix="/seed", tags=["seed"])
# logger = logging.getLogger(__name__)

# vdb_travel = VectorDBClient(collection_name="travel_docs")

# @router.post("/travel-docs")
# async def seed_travel_docs() -> Dict[str, Any]:
#     """
#     Loads db_service/app/seed/travel_docs_seed.json and upserts into travel_docs.
#     Idempotent because doc_ids are stable (we delete+add on upsert).
#     """
#     seed_path = Path(__file__).resolve().parents[1] / "seed" / "travel_docs_seed.json"
#     if not seed_path.exists():
#         return {"status": "error", "error": f"seed file not found: {seed_path}"}

#     payload = json.loads(seed_path.read_text(encoding="utf-8"))
#     docs = payload.get("docs") or []

#     upserted = await vdb_travel.bulk_upsert_travel_docs(docs=docs)
#     return {"status": "ok", "upserted": upserted}

from fastapi import APIRouter
from typing import Any, Dict
import logging

router = APIRouter(prefix="/seed", tags=["seed"])
logger = logging.getLogger(__name__)

@router.post("/travel-docs")
async def seed_travel_docs() -> Dict[str, Any]:
    """
    Disabled: With pgvector, db-service no longer generates embeddings.
    Seeding curated travel docs must be done by a worker that computes embeddings
    and calls POST /vdb/travel-docs/upsert-batch with embeddings included.
    """
    return {
        "status": "disabled",
        "message": (
            "Seeding is disabled in db-service when using pgvector. "
            "Seed via worker: compute embeddings and call /vdb/travel-docs/upsert-batch."
        ),
    }

