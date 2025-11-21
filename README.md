# Travel AI Platform

AI-powered travel planning agent with personalized trip recommendations.

## Architecture

This platform consists of 3 microservices:

1. **Gateway Service** (Port 8000) - REST API, handles user requests
2. **Worker Service** - Background processor, orchestrates trip planning
3. **DB Service** (Port 8001) - Database access layer

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Queue**: Redis
- **Database**: PostgreSQL
- **Vector DB**: LanceDB
- **LLM**: OpenAI / Anthropic

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+

### Local Development
