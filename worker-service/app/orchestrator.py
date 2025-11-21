"""
Orchestrator coordinates the workflow:
Request Handler → Context Manager → Data Retriever → Filter Engine → LLM Module
"""
from app.modules.request_handler import RequestHandler
from app.modules.context_manager import ContextManager
from app.modules.data_retriever import DataRetriever
from app.modules.filter_engine import FilterEngine
from app.modules.llm_module import LLMModule

class TripOrchestrator:
    def __init__(self):
        self.request_handler = RequestHandler()
        self.context_manager = ContextManager()
        self.data_retriever = DataRetriever()
        self.filter_engine = FilterEngine()
        self.llm_module = LLMModule()

    async def process_trip_request(self, raw_request):
        # Step 1: Normalize request
        normalized = await self.request_handler.normalize(raw_request)

        # Step 2: Build context
        context_pack = await self.context_manager.build_context(normalized)

        # Step 3: Retrieve data
        grounded_context = await self.data_retriever.retrieve(context_pack)

        # Step 4: Filter candidates
        candidates_pack = await self.filter_engine.filter_and_rank(grounded_context, context_pack)

        # Step 5: Generate trip plan
        trip_response = await self.llm_module.generate_plan(candidates_pack, context_pack)

        # TODO: Save response to DB, send to queue, etc.
        return trip_response
