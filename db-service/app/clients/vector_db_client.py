# app/clients/vector_db_client.py
from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


from app.config import get_settings

logger = logging.getLogger(__name__)
S = get_settings()


class VectorDBClient:
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "memories",
        embedding_model: Optional[str] = None,
    ):
        self.persist_dir = (
            persist_dir
            or os.getenv("VECTOR_PERSIST_DIR")
            or "/app/.chroma"
        )
        os.makedirs(self.persist_dir, exist_ok=True)

        # Use a free local embedding model from Hugging Face
        model_name = embedding_model or os.getenv(
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        )

        logger.info("VectorDBClient: using HF embeddings model=%s", model_name)

        self.embeddings = HuggingFaceEmbeddings(model_name=model_name)

        self.store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
        )

        logger.info(
            "VectorDBClient initialized with persist_dir=%s, collection=%s",
            self.persist_dir,
            collection_name,
        )


    # -------------------------------------------------------------------------
    # Upserts
    # -------------------------------------------------------------------------

    async def upsert_message(
        self,
        *,
        thread_id: str,
        message_id: str,
        text: str,
        role: str,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Upsert one message into the vector store.

        Uses a stable id (`{thread_id}:{message_id}`) so we can overwrite safely.
        Metadata:
          {
            "thread_id": ...,
            "message_id": ...,
            "role": "user" | "assistant",
            ...
          }
        """
        if not text:
            return

        doc_id = f"{thread_id}:{message_id}"
        meta: Dict[str, Any] = {
            "thread_id": thread_id,
            "message_id": message_id,
            "role": role,
        }
        if extra_meta:
            meta.update(extra_meta)

        logger.info(
            "VDB upsert_message: thread_id=%s message_id=%s role=%s",
            thread_id,
            message_id,
            role,
        )

        # emulate "upsert" by deleting existing id first
        def _upsert():
            try:
                self.store.delete(ids=[doc_id])
            except Exception:
                # it's fine if it didn't exist
                pass

            doc = Document(page_content=text, metadata=meta)
            self.store.add_documents([doc], ids=[doc_id])

        await asyncio.to_thread(_upsert)

    async def bulk_upsert_messages(
        self,
        *,
        thread_id: str,
        messages: List[Dict[str, Any]],
    ) -> None:
        """
        Insert a batch of messages (e.g., a recent window) for this thread.
        """
        docs: List[Document] = []
        ids: List[str] = []

        for m in messages:
            text = m.get("text") or m.get("content") or ""
            if not text:
                continue
            mid = m.get("message_id") or m.get("id") or ""
            if not mid:
                continue

            doc_id = f"{thread_id}:{mid}"
            meta = {
                "thread_id": thread_id,
                "message_id": mid,
                "role": m.get("role"),
            }
            docs.append(Document(page_content=text, metadata=meta))
            ids.append(doc_id)

        if not docs:
            return

        logger.info(
            "VDB bulk_upsert_messages: thread_id=%s count=%s",
            thread_id,
            len(docs),
        )

        def _bulk_upsert():
            try:
                self.store.delete(ids=ids)
            except Exception:
                pass

            self.store.add_documents(docs, ids=ids)

        await asyncio.to_thread(_bulk_upsert)

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    async def query_memories(
        self,
        *,
        thread_id: str,
        query_text: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k semantically relevant snippets for this thread.
        Returns a list of dicts:
          { "text": ..., "metadata": {...}, "score": float }
        """
        if not query_text:
            return []

        logger.info(
            "VDB query_memories: thread_id=%s top_k=%s query=%s",
            thread_id,
            top_k,
            query_text[:120],
        )

        # similarity_search_with_relevance_scores is sync; run in a worker thread
        def _search():
            return self.store.similarity_search_with_relevance_scores(
                query_text,
                k=top_k,
                filter={"thread_id": thread_id},
            )

        results = await asyncio.to_thread(_search)

        out: List[Dict[str, Any]] = []
        for doc, score in results:
            out.append(
                {
                    "text": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                }
            )
        return out

    # -------------------------------------------------------------------------
    # Debug helpers
    # -------------------------------------------------------------------------

    def list_all_docs(self, k: int = 10) -> List[Dict[str, Any]]:
        """
        Return a small sample of docs from the Chroma collection
        so we can verify what's stored. (Debug / admin use)
        """
        try:
            coll = self.store._collection  # underlying Chroma collection
            peek = coll.peek(k)
            docs = []
            for i in range(len(peek["ids"])):
                docs.append(
                    {
                        "id": peek["ids"][i],
                        "text": peek["documents"][i],
                        "metadata": peek["metadatas"][i],
                    }
                )
            return docs
        except Exception as e:
            logger.exception("Error listing docs from vector DB: %s", e)
            return []

    async def delete_all_memories(self) -> int:
        """
        Delete ALL documents from this Chroma collection.
        Returns number of deleted docs (best-effort). Debug / admin only.
        """
        logger.warning("VDB: deleting ALL memories from collection")

        def _delete_all():
            try:
                coll = self.store._collection
                count_before = coll.count()
                coll.delete(where={})  # delete everything
                count_after = coll.count()
                return count_before - count_after
            except Exception as e:
                logger.exception("VDB delete_all_memories failed: %s", e)
                return 0

        deleted = await asyncio.to_thread(_delete_all)
        logger.info("VDB: deleted ~%s memories", deleted)
        return deleted

    async def delete_thread_memories(self, thread_id: str) -> int:
        """
        Delete all memories associated with a specific thread_id.
        Returns number of deleted docs. Debug / admin only.
        """
        logger.warning("VDB: deleting memories for thread_id=%s", thread_id)

        def _delete_thread():
            try:
                coll = self.store._collection
                peek = coll.get(where={"thread_id": thread_id})
                ids = peek.get("ids", []) or []
                if not ids:
                    return 0
                coll.delete(ids=ids)
                return len(ids)
            except Exception as e:
                logger.exception("VDB delete_thread_memories failed: %s", e)
                return 0

        deleted = await asyncio.to_thread(_delete_thread)
        logger.info("VDB: deleted %s memories for thread_id=%s", deleted, thread_id)
        return deleted
    
    # -------------------------------------------------------------------------
    # Travel docs (curated RAG)
    # -------------------------------------------------------------------------

    async def upsert_travel_doc(
        self,
        *,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        if not text or not doc_id:
            return

        meta = dict(metadata or {})
        meta.setdefault("doc_id", doc_id)
        meta.setdefault("source", "curated")

        logger.info("VDB upsert_travel_doc: doc_id=%s", doc_id)

        def _upsert():
            try:
                self.store.delete(ids=[doc_id])
            except Exception:
                pass
            doc = Document(page_content=text, metadata=meta)
            self.store.add_documents([doc], ids=[doc_id])

        await asyncio.to_thread(_upsert)

    async def bulk_upsert_travel_docs(
        self,
        *,
        docs: List[Dict[str, Any]],
    ) -> int:
        """
        docs: [{ "doc_id": str, "text": str, "metadata": {...} }, ...]
        """
        chroma_docs: List[Document] = []
        ids: List[str] = []

        for d in docs:
            doc_id = d.get("doc_id") or d.get("id")
            text = d.get("text") or ""
            meta = d.get("metadata") or {}
            if not doc_id or not text:
                continue

            meta = dict(meta)
            meta.setdefault("doc_id", doc_id)
            meta.setdefault("source", "curated")

            chroma_docs.append(Document(page_content=text, metadata=meta))
            ids.append(doc_id)

        if not chroma_docs:
            return 0

        logger.info("VDB bulk_upsert_travel_docs: count=%s", len(chroma_docs))

        def _bulk():
            try:
                self.store.delete(ids=ids)
            except Exception:
                pass
            self.store.add_documents(chroma_docs, ids=ids)

        await asyncio.to_thread(_bulk)
        return len(chroma_docs)

    async def query_travel_docs(
        self,
        *,
        query_text: str,
        top_k: int = 8,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query_text:
            return []

        logger.info(
            "VDB query_travel_docs: top_k=%s where=%s query=%s",
            top_k,
            where,
            query_text[:120],
        )

        def _search():
            return self.store.similarity_search_with_relevance_scores(
                query_text,
                k=top_k,
                filter=where if where else None,
            )

        results = await asyncio.to_thread(_search)

        out: List[Dict[str, Any]] = []
        for doc, score in results:
            out.append({"text": doc.page_content, "metadata": doc.metadata, "score": float(score)})
        return out

    

    async def close(self) -> None:
        """
        Nothing special to close for the LangChain Chroma wrapper,
        but we keep this for API symmetry.
        """
        pass



