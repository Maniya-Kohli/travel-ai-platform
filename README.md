# Travel AI Platform

AI-powered travel planning agent that turns natural-language requests into structured, personalized trip itineraries.

---

## Architecture

The system consists of **3 core backend microservices** plus shared infrastructure:

1. **Gateway Service** (FastAPI, Port `8000`)  
   - Public REST API & WebSocket entrypoint.  
   - Accepts raw user messages and trip constraints.  
   - Enqueues work items into Redis for the worker.  
   - Returns request IDs so clients can poll or subscribe for results.

2. **Worker Service** (Background processor)  
   - Listens to the Redis queue for incoming trip-planning jobs.  
   - Validates and normalizes raw requests into a `NormalizedMessage` (dates, destination, constraints, etc.).
   - Implements RAG pipeline , manages context
   - Calls the configured LLM provider (OpenAI / Anthropic) to generate a structured `trip_plan`.  
   - Stores messages and trip plans in PostgreSQL + LanceDB.  

3. **DB Service** (FastAPI, Port `8001`)  
   - Thin database access layer over PostgreSQL and LanceDB.  
   - Exposes endpoints for:
     - Threads & messages
     - Normalized messages
     - Trip plans / itineraries
   - Encapsulates all ORM / SQL logic so other services only talk to it via HTTP.

### Supporting Infrastructure

- **Redis** – Message queue between Gateway and Worker.
- **PostgreSQL** – Primary relational store for:
  - Threads, raw messages
  - Normalized messages
  - Trip plans / metadata
- **LanceDB** – Vector database for:
  - Embeddings (e.g. POIs, previous trips, retrieval-augmented planning).
- **LLM Providers** – pluggable:
  - OpenAI (GPT)
  - Gemini
  - Others can be wired in behind a common interface.

---

## Tech Stack

### Language & Framework

- **Python** `3.11+`
- **FastAPI** for HTTP APIs (Gateway & DB Service)
- **Pydantic** models for strict request / response schemas

### Data & Storage

- **PostgreSQL**
  - Core relational data (threads, messages, normalized messages, trip plans).
- **LanceDB**
  - Vector storage for semantic retrieval (POIs, prior trips, embeddings).
- **SQLAlchemy / Alembic**
  - ORM + migrations (if present in your project; adjust if you’re using something else).

### Messaging & Background Processing

- **Redis**
  - Simple job queue between Gateway and Worker.
  - Supports at-least-once processing pattern.

### AI / LLM

- **OpenAI / Anthropic** (configurable)
  - Used by the Worker Service to generate structured `trip_plan` JSON.
  - Abstracted behind an internal LLM module so you can swap models without changing business logic.

### Containerization & DevOps

- **Docker / Docker Compose**
  - All services + infrastructure run as containers.
  - Single command to spin up full stack.
- (Optional) **Makefile / scripts**
  - For common tasks (formatting, tests, migrations).
