# Worker Service

Background microservice for orchestrating the AI travel agent workflow.

## Responsibilities

- Orchestrates context, retrieval, filtering, LLM calls
- Listens for requests (via queue)
- Integrates with DB service and other backend APIs

## Tech Stack

- Python, FastAPI
- Redis (queue)
- LangChain + OpenAI for LLM/integrated memory
- HTTPx for API calls
