# gateway-service/app/clients/db_service_client.py
import httpx
from typing import List, Dict, Any
from app.config import get_settings

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
