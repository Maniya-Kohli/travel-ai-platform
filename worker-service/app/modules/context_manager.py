"""
Builds user/context pack (constraints, memory) for workflow.
Fetches recent messages from DB Service for conversation context.
"""
from app.clients.db_service_client import DBServiceClient


class ContextManager:
    def __init__(self):
        self.db_client = DBServiceClient()
    
    async def build_context(self, normalized_request):
        """
        Build context pack with conversation history
        
        Args:
            normalized_request: Normalized trip request
            
        Returns:
            context_pack: Dict with constraints and memory
        """
        thread_id = normalized_request.get("thread_id")
        
        # Fetch recent messages if thread exists
        recent_messages = []
        if thread_id:
            try:
                recent_messages = await self.db_client.get_thread_messages(
                    thread_id,
                    limit=10  # Last 10 messages
                )
            except Exception as e:
                print(f"Warning: Could not fetch messages: {e}")
        
        # Build context pack
        context_pack = {
            "thread_id": thread_id,
            "constraints": normalized_request.get("constraints", {}),
            "memory": {
                "recent_messages": recent_messages,
                "long_term_memories": []  # TODO: Add vector DB integration
            },
            "api_intents": [],  # TODO: Build based on constraints
            "cache_keys": {}  # TODO: Generate cache keys
        }
        
        return context_pack
    
    async def close(self):
        """Cleanup resources"""
        await self.db_client.close()
