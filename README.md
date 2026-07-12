# Industrial AI Agent for Semiconductor Manufacturing

Industrial AI Agent is an independently developed full-stack portfolio project
for exploring traceable AI-assisted manufacturing workflows. The repository
uses fictional equipment identities, synthetic context, and configurable local
or external OpenAI-compatible services. It does not contain production data or
proprietary system material.

## Current status

**In Progress — v0.1 foundation closeout**

The conversation foundation is runnable and tested. It includes FastAPI,
SQLite persistence, explicit Alembic migrations, an OpenAI-compatible chat
adapter, synchronous and SSE message flows, and a React workbench for
conversation history and context editing.

Two follow-up milestones are also implemented:

- **v0.1.1 — Streaming Conversation:** incremental SSE responses, client-side
  cancellation, explicit stream errors, and persistence only after the backend
  consumes a complete non-empty assistant response.
- **v0.1.2 — Industrial Chat Workspace UI:** a Dithered Ant Design shell,
  responsive navigation, a single-scroll conversation layout, message states,
  and conversation-bound synthetic context.

The remaining v0.1 acceptance item is a clean-environment setup verification.
LangGraph remains planned for v0.2.

See the [implementation status](docs/implementation-status.md) for the
code-backed feature matrix and the [roadmap](docs/roadmap.md) for milestone
boundaries.

## What is implemented

- conversation create, list, open, and permanent delete;
- chronological user and assistant message persistence;
- synchronous and SSE assistant-response endpoints;
- conversation history passed to the configured model for continued dialogue;
- conversation-bound device, lot, time-range, environment, and data-source
  context;
- a deterministic catalog of three fictional devices for context selection;
- API-process health reporting;
- desktop and mobile conversation navigation;
- loading, empty, unavailable, streaming, cancellation, and retry states; and
- a dark Ant Design workbench with restrained Dithered accents.

The current assistant is still a general OpenAI-compatible chat flow. Device
selection does not query equipment, and the project does not yet calculate
yield, inspect alarms, retrieve documents, call manufacturing tools, or provide
evidence-backed causal analysis.

## Project direction

The planned system will combine:

- persistent conversation and manufacturing context;
- deterministic production analytics;
- retrieval from fictional equipment documents;
- explicit LangGraph orchestration;
- visible tool, source, error, and retry events; and
- reproducible evaluation against synthetic scenarios.

Numeric manufacturing results will be calculated in domain code rather than
inferred by the language model. Answers must distinguish retrieved facts,
structured records, calculated values, model interpretation, and missing
evidence.

## Repository layout

```text
industrial-ai-agent/
├── apps/
│   ├── api/       # FastAPI, SQLAlchemy, Alembic, and LLM adapter
│   └── web/       # React, TypeScript, Vite, and Ant Design
├── data/          # Documentation only; no dataset is implemented yet
├── docs/          # Scope, implementation status, and roadmap
└── scripts/       # Added only when project automation is needed
```

LangGraph, RAG, MCP, and manufacturing-domain packages will be introduced only
when their milestones implement working behavior.

## Local development

The backend requires Python 3.12 and
[uv](https://docs.astral.sh/uv/). From `apps/api`:

```bash
uv sync --locked
uv run alembic upgrade head
uv run uvicorn industrial_agent.main:app --host 127.0.0.1 --port 8000
```

The API process can start without an LLM model. Message requests require an
OpenAI-compatible service and `LLM_MODEL`; the default base URL targets a local
Ollama-compatible endpoint.

From `apps/web`, using a compatible Node.js environment:

```bash
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. The application is then
available at the URL printed by Vite.

Detailed configuration and endpoint examples are in the
[API guide](apps/api/README.md) and [web guide](apps/web/README.md).

## Verification

```bash
cd apps/api
uv run pytest -q
uv run ruff check .
uv build

cd ../web
npm run typecheck
npm test -- --run
npm run lint
npm run build
```

The latest recorded results are listed in
[implementation status](docs/implementation-status.md). A successful local
verification is not yet treated as proof of the remaining clean-environment
acceptance item.

## Documentation

- [Documentation index](docs/README.md)
- [Project scope and publication boundaries](docs/project-scope.md)
- [Implementation status and API matrix](docs/implementation-status.md)
- [Milestone roadmap](docs/roadmap.md)

## Known limitations

- Health reports API-process availability only. It does not check the database,
  model service, or future manufacturing tools.
- The configured model receives conversation history, but workspace context is
  not yet injected into the model request.
- A failed assistant request leaves the user message persisted.
- Streaming depends on provider and proxy flushing behavior. The service
  creates an assistant record only after consuming a complete non-empty stream;
  client-disconnect persistence behavior still needs an integration test.
- Context values and device identities are synthetic metadata. They do not
  represent live equipment or production state.
- There is no LangGraph, tool calling, RAG, manufacturing dataset,
  authentication, retry orchestration, or deployment stack.
- Conversation and message history are not paginated.

## License

No license has been selected. Until a license file is added, reuse rights are
not granted.
