"""
DB Service Client
HTTP client for calling DB Service API endpoints
"""
import httpx
from typing import List, Optional, Dict, Any
from app.config import get_settings
import logging


logger = logging.getLogger(__name__)
settings = get_settings()


class DBServiceClient:
    """Client for interacting with DB Service"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.DB_SERVICE_URL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    # Thread operations
    async def create_thread(self) -> Dict:
        """Create a new conversation thread"""
        response = await self.client.post("/threads")
        response.raise_for_status()
        print(response.json())
        return response.json()
    
    async def get_thread(self, thread_id: str) -> Dict:
        """Get thread by ID"""
        response = await self.client.get(f"/threads/{thread_id}")
        response.raise_for_status()
        return response.json()
    
    async def delete_thread(self, thread_id: str):
        """Delete thread by ID"""
        response = await self.client.delete(f"/threads/{thread_id}")
        response.raise_for_status()
    
    # Message operations
    async def create_normalised_message(
        self,
        thread_id: str,
        message_id : str , 
        content: Dict[str, any]
    ) -> Dict:
        response = await self.client.post(
            "/normalised_messages",
            json={
                "thread_id": thread_id,
                "message_id" : message_id, 
                "content": content
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def create_message(
        self,
        thread_id: str,
        role: str,
        content: Dict[str, any]
    ) -> Dict:
        response = await self.client.post(
            "/messages",
            json={
                "thread_id": thread_id,
                "role": role,
                "content": content
            }
        )
        response.raise_for_status()
        return response.json()

    
    async def get_message(self, message_id: str) -> Dict:
        """Get message by ID"""
        response = await self.client.get(f"/messages/{message_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_thread_messages(
        self,
        thread_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict]:
        """Get all messages in a thread"""
        response = await self.client.get(
            f"/messages/thread/{thread_id}",
            params={"skip": skip, "limit": limit}
        )
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> Dict:
        """Check DB Service health"""
        response = await self.client.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def get_thread_messages(self, *, thread_id: str, skip: int = 0, limit: int = 20) -> List[Dict[str, any]]:
        resp = await self.client.get(
            "/messages",
            params={"thread_id": thread_id, "skip": skip, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()


    # ----------------------
    # Vector DB (proxied via db-service /vdb routes)
    # ----------------------
    async def upsert_memory(
        self,
        *,
        thread_id: str,
        message_id: str,
        text: str,
        role: str,
        embedding: list[float],              # ✅ required now
        extra_meta: Optional[Dict[str, any]] = None,
    ) -> None:
        payload = {
            "thread_id": thread_id,
            "message_id": message_id,
            "text": text,
            "role": role,
            "embedding": embedding,          # ✅ add this
            "extra_meta": extra_meta or {},
        }
        resp = await self.client.post("/vdb/memories", json=payload)
        resp.raise_for_status()


    async def query_memories(
        self,
        *,
        thread_id: str,
        query_embedding: List[float],   # ✅ change
        top_k: int = 5,
    ) -> List[Dict[str, any]]:
        resp = await self.client.post(
            "/vdb/memories/search",
            json={
                "thread_id": thread_id,
                "query_embedding": query_embedding,
                "top_k": top_k,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])



    async def query_travel_docs(
        self,
        *,
        query_embedding: Optional[List[float]] = None,
        query: Optional[str] = None,
        top_k: int = 8,
        region_code: Optional[str] = None,
        pet_friendly: Optional[bool] = None,
        doc_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        if not query_embedding and not query:
            return []

        payload: Dict[str, Any] = {"top_k": top_k}

        # send ONE of these (prefer embedding if provided)
        if query_embedding:
            payload["query_embedding"] = query_embedding
        else:
            payload["query_text"] = query  # or "query" depending on your FastAPI model

        if region_code:
            payload["region_code"] = region_code
        if pet_friendly is not None:
            payload["pet_friendly"] = pet_friendly
        if doc_type:
            payload["doc_type"] = doc_type

        resp = await self.client.post("/vdb/travel-docs/search", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])


