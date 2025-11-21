# DB Service

Database access layer for Travel AI Platform.

## Purpose

Manages all database operations for the platform:

- Thread management (conversation threads)
- Message storage (user/assistant messages)
- Memory operations (long-term user preferences)

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy

## API Endpoints

### Health

- `GET /health` - Service health check

### Threads

- `GET /threads` - List all threads
- `GET /threads/{thread_id}` - Get thread by ID
- `POST /threads` - Create new thread
- `GET /threads/{thread_id}/messages` - Get thread messages

### Messages

- `GET /messages/{message_id}` - Get message by ID
- `POST /messages` - Create new message

## Local Development

### Setup
