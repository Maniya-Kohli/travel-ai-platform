# app/clients/vector_db_client.py  (pgvector version)
from __future__ import annotations

import os
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional

import psycopg2
from pgvector.psycopg2 import register_vector
from pgvector import Vector


logger = logging.getLogger(__name__)


class VectorDBClient:
    """
    Stores + searches vectors in Postgres using pgvector.
    NOTE: db-service does NOT generate embeddings anymore.
    Caller must provide:
      - embedding (for upsert)
      - query_embedding (for search)
    This keeps Render memory low.
    """

    def __init__(self):
        self.db_url = os.environ["DATABASE_URL"]

    def _conn(self):
        conn = psycopg2.connect(self.db_url)
        register_vector(conn)
        return conn

    # -------------------------------------------------------------------------
    # Upserts (Memories)
    # -------------------------------------------------------------------------
    async def upsert_message(
        self,
        *,
        thread_id: str,
        message_id: str,
        text: str,
        role: str,
        embedding: List[float],
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not text:
            return

        doc_id = f"{thread_id}:{message_id}"
        meta: Dict[str, Any] = {"thread_id": thread_id, "message_id": message_id, "role": role}
        if extra_meta:
            meta.update(extra_meta)

        def _upsert():
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vectors (id, kind, thread_id, content, metadata, embedding)
                    VALUES (%s, 'memory', %s, %s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      content = EXCLUDED.content,
                      metadata = EXCLUDED.metadata,
                      embedding = EXCLUDED.embedding
                    """,
                    (doc_id, thread_id, text, json.dumps(meta), embedding),
                )

        await asyncio.to_thread(_upsert)

    async def bulk_upsert_messages(
        self,
        *,
        thread_id: str,
        messages: List[Dict[str, Any]],
    ) -> None:
        """
        messages must include an 'embedding' field (List[float]) for each message.
        """
        rows = []
        for m in messages:
            text = m.get("text") or m.get("content") or ""
            mid = m.get("message_id") or m.get("id") or ""
            emb = m.get("embedding")
            if not text or not mid or not emb:
                continue

            doc_id = f"{thread_id}:{mid}"
            meta = {"thread_id": thread_id, "message_id": mid, "role": m.get("role")}
            rows.append((doc_id, thread_id, text, json.dumps(meta), emb))

        if not rows:
            return

        def _bulk():
            with self._conn() as conn, conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO vectors (id, kind, thread_id, content, metadata, embedding)
                    VALUES (%s, 'memory', %s, %s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      content = EXCLUDED.content,
                      metadata = EXCLUDED.metadata,
                      embedding = EXCLUDED.embedding
                    """,
                    rows,
                )

        await asyncio.to_thread(_bulk)

    # -------------------------------------------------------------------------
    # Query (Memories)
    # -------------------------------------------------------------------------
    async def query_memories(
        self,
        *,
        thread_id: str,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        if not query_embedding:
            return []

        def _search():
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, metadata, 1 - (embedding <=> %s) AS score
                    FROM memories
                    WHERE thread_id = %s
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (Vector(query_embedding), thread_id, Vector(query_embedding), top_k),
                )
                rows = cur.fetchall()
            return [{"text": c, "metadata": m, "score": float(s)} for c, m, s in rows]

        return await asyncio.to_thread(_search)

    # -------------------------------------------------------------------------
    # Debug helpers (pgvector versions)
    # -------------------------------------------------------------------------
    def list_all_docs(self, k: int = 10) -> List[Dict[str, Any]]:
        def _list():
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, content, metadata
                    FROM vectors
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (k,),
                )
                rows = cur.fetchall()
            return [{"id": i, "text": c, "metadata": m} for i, c, m in rows]

        return _list()

    async def delete_all_memories(self) -> int:
        def _delete_all():
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM vectors WHERE kind='memory'")
                return cur.rowcount

        return await asyncio.to_thread(_delete_all)

    async def delete_thread_memories(self, thread_id: str) -> int:
        def _delete_thread():
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM vectors WHERE kind='memory' AND thread_id=%s", (thread_id,))
                return cur.rowcount

        return await asyncio.to_thread(_delete_thread)

    # -------------------------------------------------------------------------
    # Travel docs (curated RAG)
    # -------------------------------------------------------------------------
    async def upsert_travel_doc(
        self,
        *,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
        embedding: List[float],
    ) -> None:
        if not text or not doc_id:
            return

        meta = dict(metadata or {})
        meta.setdefault("doc_id", doc_id)
        meta.setdefault("source", "curated")

        def _upsert():
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vectors (id, kind, thread_id, content, metadata, embedding)
                    VALUES (%s, 'travel_doc', NULL, %s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      content = EXCLUDED.content,
                      metadata = EXCLUDED.metadata,
                      embedding = EXCLUDED.embedding
                    """,
                    (doc_id, text, json.dumps(meta), embedding),
                )

        await asyncio.to_thread(_upsert)

    async def bulk_upsert_travel_docs(
        self,
        *,
        docs: List[Dict[str, Any]],
    ) -> int:
        rows = []
        for d in docs:
            doc_id = d.get("doc_id") or d.get("id")
            text = d.get("text") or ""
            meta = d.get("metadata") or {}
            emb = d.get("embedding")
            if not doc_id or not text or not emb:
                continue

            meta = dict(meta)
            meta.setdefault("doc_id", doc_id)
            meta.setdefault("source", "curated")
            rows.append((doc_id, text, json.dumps(meta), emb))

        if not rows:
            return 0

        def _bulk():
            with self._conn() as conn, conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO vectors (id, kind, thread_id, content, metadata, embedding)
                    VALUES (%s, 'travel_doc', NULL, %s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      content = EXCLUDED.content,
                      metadata = EXCLUDED.metadata,
                      embedding = EXCLUDED.embedding
                    """,
                    rows,
                )

        await asyncio.to_thread(_bulk)
        return len(rows)

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

    async def close(self) -> None:
        return
