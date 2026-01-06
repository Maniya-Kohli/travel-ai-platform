# gateway-service/app/clients/db_service_client.py
import httpx
from typing import List, Dict, Any, Optional
from app.config import get_settings
import asyncio
import json

settings = get_settings()


class DBServiceClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.DB_SERVICE_URL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def get_thread_messages(
        self, thread_id: str, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        resp = await self.client.get(
            f"/messages/thread/{thread_id}",
            params={"skip": skip, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()
    
    async def query_travel_docs(
        self,
        *,
        query_embedding: List[float],
        top_k: int = 8,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query_embedding:
            return []

        where = where or {}

        def _search():
            with self._conn() as conn, conn.cursor() as cur:
                if where:
                    cur.execute(
                        """
                        SELECT content, metadata, 1 - (embedding <=> %s::vector) AS score
                        FROM vectors
                        WHERE kind='travel_doc' AND metadata @> %s::jsonb
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (query_embedding, json.dumps(where), query_embedding, top_k),
                    )
                else:
                    cur.execute(
                        """
                        SELECT content, metadata, 1 - (embedding <=> %s::vector) AS score
                        FROM vectors
                        WHERE kind='travel_doc'
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (query_embedding, query_embedding, top_k),
                    )
                rows = cur.fetchall()

            return [{"text": c, "metadata": m, "score": float(s)} for c, m, s in rows]

        return await asyncio.to_thread(_search)

