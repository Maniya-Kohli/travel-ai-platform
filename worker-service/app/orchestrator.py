# app/modules/trip_orchestrator.py (or wherever this class lives)
import json
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
        """
        print(f"🔄 Worker service : Processing request: {raw_request} ")
        
        try:
            # Step 1: Normalize request
            normalized = await self.request_handler.normalize(raw_request)
            json_ready = normalized.model_dump(mode="json")

            await self.db_client.create_normalised_message(
                thread_id=normalized.thread_id,
                message_id=normalized.message_id,
                content=json_ready,
            )
            print("✓ Request normalized")

            # Step 2: Build context (fetches messages from DB + VDB)
            context_pack = await self.context_manager.build_context(normalized)
            print("✓ Context built")

            # Step 3: Retrieve data
            grounded_context = await self.data_retriever.retrieve(context_pack)
            print("✓ Data retrieved")

            # # Step 4: Filter candidates
            # candidates_pack = await self.filter_engine.filter_and_rank(
            #     grounded_context,
            #     context_pack,
            # )
            # print("✓ Candidates filtered")

            # Step 5: Generate trip plan
            trip_response = await self.llm_module.generate_plan(
                grounded_context,
                context_pack,
            )
            print("✓ Trip plan generated" , trip_response)

            # Step 6: Save assistant response to DB
            thread_id = context_pack.get("thread_id")
            if thread_id:
                # Handle both Pydantic models and plain dicts
                if hasattr(trip_response, "model_dump"):
                    json_ready = trip_response.model_dump(mode="json")
                else:
                    json_ready = trip_response  # already a dict / JSON-compatible

                print("Assistant response payload type:", type(json_ready), thread_id , json_ready)
                await self.db_client.create_message(
                    thread_id=thread_id,
                    role="assistant",
                    content=json_ready,
                )
                print("✓ Response saved to DB")

            return trip_response

        except Exception as e:
        # 🔴 Persist debug info (very useful!)
            try:
                thread_id = raw_request.get("thread_id")
                debug_payload = {
                    "type": "orchestrator_error",
                    "request_id": raw_request.get("request_id"),
                    "thread_id": thread_id,
                    "error": str(e),
                    # be careful to avoid huge blobs; you can trim or summarize:
                    "context_pack": (context_pack if "context_pack" in locals() else None),
                    "grounded_context": (
                        grounded_context if "grounded_context" in locals() else None
                    ),
                }
                if thread_id:
                    await self.db_client.create_message(
                        thread_id=thread_id,
                        role="system",
                        content=debug_payload,
                    )
            except Exception as log_err:
                print("⚠️ Failed to store debug info:", log_err)
                raise

    async def close(self):
        """Cleanup resources"""
        await self.context_manager.close()
        await self.db_client.close()
