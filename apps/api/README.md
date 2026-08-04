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
- synchronous and SSE assistant-response endpoints;
- a compiled typed LangGraph workflow for synchronous execution, with the SSE
  runner reusing its state and execution-step boundaries;
- standalone OpenAI-compatible chat adapter with configurable endpoint,
  optional API key, model, and timeout;
- typed OpenAI-compatible tool-call support for one
  `get_production_summary` call;
- deterministic production-summary execution over a fictional AOI dataset and
  evidence handoff for final synchronous and SSE model responses;
- conversation-bound Workspace Context `GET` and `PATCH` endpoints;
- deterministic fictional device catalog and device-ID validation;
- an independent local stdio MCP server for production summary, recorded
  equipment status, and defect distribution tools;
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

## Local MCP server

The MCP entrypoint is separate from FastAPI and communicates over stdio:

```bash
uv run industrial-agent-mcp
```

Configure a local MCP client with `uv` as the command, `run
industrial-agent-mcp` as the arguments, and this `apps/api` directory as the
working directory. The server exposes `get_production_summary`,
`get_equipment_status`, and `get_defect_distribution`. Their input and output
schemas come from the same Pydantic contracts used by the native Python tools.

Each call requires explicit synthetic equipment, lot when applicable, and UTC
time input. The MCP boundary does not read conversation context or invoke the
LLM, LangGraph, FastAPI, or document retrieval. It also provides no HTTP
transport, authentication, remote deployment, or live manufacturing data.

The backend pins the official Python MCP SDK to the supported 1.x line. The
server uses its low-level API because this boundary must reject unsupported
input fields at runtime as well as publish `additionalProperties: false` in
discovery schemas.

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

This endpoint stores the user's message, loads the complete chronological
history through the graph, sends it to the configured adapter, then stores one
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
adapter. It sends synchronous or streaming requests to the standard
`/v1/chat/completions` endpoint and accepts `user` and `assistant` history.
For a supported synchronous production question, it can also send one tool
definition, parse one tool call, append the tool evidence, and request the
final assistant response. The HTTP Message API persists one assistant Message
for each successful exchange.

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

# Optional. Defaults to LLM_MODEL when empty.
LLM_ROUTER_MODEL=<router-or-answer-model>

# Default: 10 seconds. Accepted range: 1 through 30 seconds.
LLM_ROUTER_TIMEOUT_SECONDS=10
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

The answer adapter raises a configuration error for a missing model, a connection
error for timeout or transport failures, a service error for non-success HTTP
responses, and a response error for malformed or empty completion payloads.
It does not start Ollama, download models, or inspect whether the configured
model is installed. The routing classifier retries one timeout, transient
transport failure, or invalid structured response; answer and evidence-tool
requests are not retried. Streaming uses the dedicated Message API
endpoint and does not persist partial assistant output.

## Workspace Context API

Each Conversation stores synthetic workspace metadata. New records default to
the `synthetic` environment and `synthetic_demo` data source; device, lot, and
time range remain empty until selected.

```bash
curl \
  http://127.0.0.1:8000/conversations/<conversation-id>/context

curl -X PATCH \
  http://127.0.0.1:8000/conversations/<conversation-id>/context \
  -H 'Content-Type: application/json' \
  -d '{"device":"AOI-WAFER-01","lot":"LOT-DEMO-01","time_range":"Last 4 hours"}'

curl http://127.0.0.1:8000/devices
```

The device catalog contains three deterministic fictional identities. The
graph can fill missing production-tool arguments from the selected device, lot,
and supported synthetic time-range presets. It does not inject context into
the general model prompt; custom or unrecognized time-range labels still
require explicit UTC timestamps.

## Verify

Run the deterministic formal evaluation suite from `apps/api`:

```bash
uv run industrial-agent-eval
```

The command validates and runs the package-owned 30-scenario fixture, prints
separate per-dimension results, and writes
`.artifacts/evaluation/latest.json`. That directory is ignored by Git. A
filtered run and explicit artifact target are also supported:

```bash
uv run industrial-agent-eval \
  --scenario alarm-optical \
  --output /tmp/industrial-agent-evaluation.json
```

A filtered artifact is marked `partial`; it does not claim that the complete
suite passed. Exit status is `0` only when the selected valid scenario set
meets every applicable threshold, `1` for a completed run below threshold,
and `2` for fixture, argument, or output errors.

The JSON artifact records the fixture digest, runner version, UTC run times,
ordered scenario assertions, per-dimension summaries, sanitized failures, and
monotonic stage observations. It does not contain prompts, document bodies,
environment variables, provider configuration, or raw tracebacks. This is an
offline deterministic regression baseline. It does not call an LLM judge and
does not treat local elapsed values as a latency target.

Run the complete backend verification separately:

```bash
uv run pytest
uv run ruff check .
uv build
```

## Verification status

The documented workflow has been verified from a clean git archive copy using
the committed uv lockfile, migrations, and backend test suite.

## Non-responsibilities

Authentication and distributed deployment remain outside the implemented
scope. The v0.4 tool slice supports deterministic production
summaries, ranked defect distributions, and recorded synthetic equipment
status. Both Message endpoints use the same authoritative decision and can
execute one selected tool. Combined requests produce clarification rather than
executing multiple tools. That clarification persists two fixed
application-owned actions; selecting either action remains a normal message
request through the existing synchronous or SSE contract.

The current v0.5 retrieval slice adds `search_documents` for focused procedural
questions. It builds an explicit corpus from three protected fictional Markdown
documents and persistent local uploads, keeps chunks within section and block
boundaries, applies a fixed lexical eligibility gate, and ranks eligible chunks
with deterministic local feature-hashing vectors. It does not call an embedding
service or persist the index.

`GET /documents` lists the active corpus. `POST /documents` accepts one UTF-8
`.md` file up to 1 MiB, while `DELETE /documents/{document_id}` removes local
uploads and rejects attempts to delete built-ins. `GET
/documents/{document_id}` reads a validated built-in or local document for the
source viewer; it never accepts a filesystem path. Unknown IDs return `404`,
and unavailable storage or corpus state returns a safe `503`. When local upload
state is invalid, the list response retains built-in metadata so retrieval can
continue without hiding the failure.

Uploads are stored under the Git-ignored `apps/api/uploads/` boundary with a
small manifest. Successful upload and deletion responses are returned only
after disk state and the immutable runtime corpus agree. This is a local
development feature, not a secure shared document service.

## Dependency management

Backend metadata and runtime dependencies are declared in `pyproject.toml`.
Development tools are kept in a separate dependency group, and `uv.lock`
records the resolved environment.

## Current limitations

The API persists Conversation, user Message, and assistant Message records.
The adapter can call a configured compatible service for one supported
tool-call exchange, but has no answer retry, system prompt, or model-discovery
behavior. Ambiguous routing requires exactly one valid `classify_request` tool
call. LangGraph provides a compiled synchronous workflow with one authoritative
route and one selected tool execution. The SSE endpoint
supports production summaries, ranked defect distributions, and recorded
equipment status. Focused document questions use the same flow with retrieved
source evidence, emitting routing progress, `tool_call_started`, `tool_result`,
final text, and completion events. Its
grounded answer is forwarded as a provider-token stream after a successful
tool result. If that answer fails deterministic citation or numeric checks, the
API keeps the valid evidence and returns a route-specific message explaining
that the generated answer could not be verified. Message history
has no pagination or individual mutation operations. The health
endpoint reports API-process availability only and does not check the database
or LLM service. The synchronous endpoint remains available. The v0.1.1
streaming endpoint is `POST /conversations/{conversation_id}/messages/stream`
and returns SSE events for `message_started`, routing progress, `token`,
`message_completed`, and `error`. An evidence route can additionally emit
`tool_call_started` and `tool_result`. Only a non-empty completed assistant
response is persisted.

The conversation-bound Workspace Context contract provides `GET` and `PATCH`
endpoints at `/conversations/{conversation_id}/context`. It stores optional
device, lot, and time-range values with truthful synthetic defaults. It does
not query production systems or infer context automatically.

`GET /devices` returns a deterministic catalog of fictional synthetic device
identifiers for context selection. The catalog contains identity metadata only.
Recorded status evidence comes from the separate synthetic scenario and does
not represent live connectivity or current production machinery.
