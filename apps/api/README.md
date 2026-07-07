# API

## Purpose

This application provides the HTTP backend for the Industrial AI Agent
portfolio project.

## Implemented

- FastAPI application factory;
- environment-based application settings;
- `GET /health` process-health contract;
- synchronous SQLAlchemy and SQLite session foundation;
- explicit Alembic migration workflow;
- persisted Conversation model with UUID identifiers and UTC timestamps;
- Conversation create, list, get, and permanent-delete endpoints;
- append-only user Message persistence and chronological history endpoints;
- database-enforced Message role, content, and cascade-delete constraints;
- standalone OpenAI-compatible chat adapter with configurable endpoint,
  optional API key, model, and timeout;
- Pytest and Ruff verification; and
- reproducible uv lockfile and package build.

## Setup

From `apps/api`:

```bash
uv sync --locked
```

## Database migrations

The default local database is `apps/api/industrial_agent.db` when commands are
run from `apps/api`. Apply and reverse schema state explicitly:

```bash
uv run alembic upgrade head
uv run alembic downgrade base
```

API startup does not run migrations or create schema objects.

## Run

```bash
uv run uvicorn industrial_agent.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

The process-health endpoint is available at `http://127.0.0.1:8000/health`.

## Conversation API

Apply the latest migration before using these endpoints. A title is optional;
when omitted, it defaults to `New conversation`. Supplied titles are trimmed
and must contain between 1 and 200 characters.

```bash
curl -X POST http://127.0.0.1:8000/conversations \
  -H 'Content-Type: application/json' \
  -d '{"title":"Yield investigation"}'

curl http://127.0.0.1:8000/conversations

curl http://127.0.0.1:8000/conversations/<conversation-id>

curl -X DELETE http://127.0.0.1:8000/conversations/<conversation-id>
```

The list returns every Conversation, with the newest records first. Deletion
is permanent. There is currently no update, rename, archive, restore, or
pagination operation.

## Message API

Messages belong to a Conversation. The public create endpoint accepts only
`content`; the backend assigns the `user` role. Content is trimmed and must
contain between 1 and 10,000 characters.

```bash
curl -X POST \
  http://127.0.0.1:8000/conversations/<conversation-id>/messages \
  -H 'Content-Type: application/json' \
  -d '{"content":"What caused the yield drop?"}'

curl \
  http://127.0.0.1:8000/conversations/<conversation-id>/messages
```

History is returned from oldest to newest. Messages are append-only, so the
API does not expose individual get, update, or delete operations. Deleting the
parent Conversation permanently removes its Messages.

This endpoint stores the user's message, sends the complete chronological
history for that Conversation to the configured adapter, then stores one
assistant response. A successful request returns both new records:

```json
{
  "user_message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "user",
    "content": "What caused the yield drop?",
    "created_at": "2026-07-30T00:00:00Z"
  },
  "assistant_message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "...",
    "created_at": "2026-07-30T00:00:01Z"
  }
}
```

When adapter configuration is missing or the compatible service cannot return
a usable answer, the endpoint returns `503` with this fixed response:

```json
{"detail":"Assistant response is temporarily unavailable"}
```

The user Message remains in history after that failure; no assistant Message
is created. This makes it possible to retry without losing the original input.

## OpenAI-compatible chat adapter

The backend provides `OpenAICompatibleChatAdapter` as a standalone Python
adapter. It sends non-streaming requests to the standard
`/v1/chat/completions` endpoint and accepts only `user` and `assistant` chat
messages. The HTTP Message API uses this adapter to request and persist one
assistant Message for each successful user Message.

Configuration uses these environment variables:

```bash
# Default: http://127.0.0.1:11434/v1
LLM_BASE_URL=http://127.0.0.1:11434/v1

# Optional. Leave empty for a local service that does not require a key.
LLM_API_KEY=

# Required when constructing the adapter.
LLM_MODEL=<installed-or-compatible-model>

# Default: 60 seconds. Must be greater than zero.
LLM_TIMEOUT_SECONDS=60
```

For example, with Ollama already running and a model already installed, this
performs one local request without changing the database:

```bash
LLM_MODEL=<installed-model> uv run python - <<'PY'
from industrial_agent.config.settings import Settings
from industrial_agent.llm.openai_compatible import OpenAICompatibleChatAdapter
from industrial_agent.llm.types import ChatMessage

with OpenAICompatibleChatAdapter.from_settings(Settings()) as adapter:
    print(adapter.complete([ChatMessage(role="user", content="Reply with OK.")]))
PY
```

The adapter raises a configuration error for a missing model, a connection
error for timeout or transport failures, a service error for non-success HTTP
responses, and a response error for malformed or empty completion payloads.
It does not start Ollama, download models, retry requests, stream responses,
or inspect whether the configured model is installed.

## Verify

```bash
uv run pytest
uv run ruff check .
uv build
```

## Remaining v0.1 responsibilities

- implement and connect the synchronous React conversation interface;
- verify critical frontend interactions and error states; and
- document the complete clean-environment workflow.

## Non-responsibilities

LangGraph, RAG, MCP, manufacturing analytics, production tools, authentication,
streaming, and distributed deployment are outside v0.1.

## Dependency management

Backend metadata and runtime dependencies are declared in `pyproject.toml`.
Development tools are kept in a separate dependency group, and `uv.lock`
records the resolved environment.

## Current limitations

The API persists Conversation, user Message, and assistant Message records.
The adapter can call a configured compatible service, but has no streaming,
retries, system prompts, tool calling, or model-discovery behavior. Message
history has no pagination or individual mutation operations. The health
endpoint reports API-process availability only and does not check the database
or LLM service. Responses remain synchronous and non-streaming in v0.1;
streaming transport and persistence semantics are planned for v0.1.1.
