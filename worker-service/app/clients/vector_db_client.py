# app/clients/vector_db_client.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple
import asyncio

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import get_settings

S = get_settings()

class VectorDBClient:
    """
    Simple long-term memory client:
      - persists a Chroma collection on disk (inside container)
      - upserts messages as Documents with thread_id metadata
      - queries top-k similar docs filtered by thread_id
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "memories",
        embedding_model: Optional[str] = None,
    ):
        # Where to store vectors on disk (mount a volume later for persistence)
        self.persist_dir = persist_dir or os.getenv("VECTOR_PERSIST_DIR", "/app/.chroma")
        os.makedirs(self.persist_dir, exist_ok=True)

        # Embeddings
        self.embeddings = OpenAIEmbeddings(
            api_key=S.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""),
            model=embedding_model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        )

        # Vector store
        self.store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
        )


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
        """
        if not text:
            return

        doc_id = f"{thread_id}:{message_id}"
        meta = {"thread_id": thread_id, "message_id": message_id, "role": role}
        if extra_meta:
            meta.update(extra_meta)

        # Chroma doesn't have a native "upsert" from LangChain wrapper; emulate:
        try:
            # delete existing if present (ignore failures)
            self.store.delete(ids=[doc_id])
        except Exception:
            pass

        doc = Document(page_content=text, metadata=meta)

        # The add_* methods are sync; run in a thread to avoid blocking the event loop
        await asyncio.to_thread(self.store.add_documents, [doc], ids=[doc_id])
        await asyncio.to_thread(self.store.persist)

    async def bulk_upsert_messages(
        self,
        *,
        thread_id: str,
        messages: List[Dict[str, Any]],
    ) -> None:
        """
        Insert the recent window (short-term) so we have a base to query against later.
        """
        docs: List[Document] = []
        ids: List[str] = []

        for m in messages:
            text = m.get("text") or m.get("content") or ""
            if not text:
                continue
            doc_id = f"{thread_id}:{m.get('message_id') or m.get('id') or ''}"
            meta = {"thread_id": thread_id, "message_id": m.get("message_id") or m.get("id"), "role": m.get("role")}
            docs.append(Document(page_content=text, metadata=meta))
            ids.append(doc_id)

        if not docs:
            return

        # best-effort clear existing conflicting ids
        try:
            await asyncio.to_thread(self.store.delete, ids=ids)
        except Exception:
            pass

        await asyncio.to_thread(self.store.add_documents, docs, ids=ids)
        await asyncio.to_thread(self.store.persist)

    async def query_memories(
        self,
        *,
        thread_id: str,
        query_text: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k semantically relevant snippets for this thread.
        """
        if not query_text:
            return []

        # LangChain Chroma wrapper supports metadata filtering via `filter=`
        # The call is sync; run on a worker thread
        results = await asyncio.to_thread(
            self.store.similarity_search_with_relevance_scores,
            query_text,  # query
            k=top_k,
            filter={"thread_id": thread_id},
        )

        # massage shape for the context_pack
        out: List[Dict[str, Any]] = []
        for doc, score in results:
            out.append({
                "text": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),
            })
        return out

    async def close(self):
        # nothing to close for Chroma wrapper
        pass

    # In your VectorDBClient
    def list_all_docs(self):
        """Print all docs in the vector DB for debugging purposes."""
        # Chroma's collection API lets you get all docs:
        all_docs = self.store.get()  # Returns dict with 'ids', 'documents', 'metadatas'
        for _id, doc, meta in zip(all_docs['ids'], all_docs['documents'], all_docs['metadatas']):
            print(f"ID: {_id}\nText: {doc}\nMetadata: {meta}\n---")
        return all_docs

