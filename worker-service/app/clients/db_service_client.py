"""
DB Service Client
HTTP client for calling DB Service API endpoints
"""
import httpx
from typing import List, Optional, Dict
from app.config import get_settings

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
        role: str,
        content: Dict[str, any]
    ) -> Dict:
        response = await self.client.post(
            "/normalised_messages",
            json={
                "thread_id": thread_id,
                "role": role,
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
            "/normalised_messages",
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
