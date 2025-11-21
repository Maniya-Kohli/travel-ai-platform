"""
Orchestrator coordinates the workflow:
Request Handler → Context Manager → Data Retriever → Filter Engine → LLM Module
"""
from app.modules.request_handler import RequestHandler
from app.modules.context_manager import ContextManager
from app.modules.data_retriever import DataRetriever
from app.modules.filter_engine import FilterEngine
from app.modules.llm_module import LLMModule
from app.clients.db_service_client import DBServiceClient


class TripOrchestrator:
    def __init__(self):
        self.request_handler = RequestHandler()
        self.context_manager = ContextManager()
        self.data_retriever = DataRetriever()
        self.filter_engine = FilterEngine()
        self.llm_module = LLMModule()
        self.db_client = DBServiceClient()

    async def process_trip_request(self, raw_request):
        """
        Main workflow orchestration
        
        Args:
            raw_request: Raw request from queue
            
        Returns:
            trip_response: Final trip plan
        """
        print(f"🔄 Processing request: {raw_request.get('request_id')}")
        
        try:
            # Step 1: Normalize request
            normalized = await self.request_handler.normalize(raw_request)
            print("✓ Request normalized")

            # Step 2: Build context (fetches messages from DB)
            context_pack = await self.context_manager.build_context(normalized)
            print("✓ Context built")

            # Step 3: Retrieve data
            grounded_context = await self.data_retriever.retrieve(context_pack)
            print("✓ Data retrieved")

            # Step 4: Filter candidates
            candidates_pack = await self.filter_engine.filter_and_rank(
                grounded_context,
                context_pack
            )
            print("✓ Candidates filtered")

            # Step 5: Generate trip plan
            trip_response = await self.llm_module.generate_plan(
                candidates_pack,
                context_pack
            )
            print("✓ Trip plan generated")
            
            # Step 6: Save assistant response to DB
            thread_id = context_pack.get("thread_id")
            if thread_id:
                await self.db_client.create_message(
                    thread_id=thread_id,
                    role="assistant",
                    content=str(trip_response)  # TODO: Format properly
                )
                print("✓ Response saved to DB")

            return trip_response
            
        except Exception as e:
            print(f"❌ Error processing request: {e}")
            # TODO: Save error state to DB
            raise
    
    async def close(self):
        """Cleanup resources"""
        await self.context_manager.close()
        await self.db_client.close()
