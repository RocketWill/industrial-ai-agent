# Industrial AI Agent for Semiconductor Manufacturing

Industrial AI Agent is an independently developed full-stack portfolio project
for exploring traceable AI-assisted manufacturing workflows. The repository
uses fictional equipment identities, synthetic context, and configurable local
or external OpenAI-compatible services. It does not contain production data or
proprietary system material.

## Current status

**In Progress — v0.5 Self-built RAG**

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

The clean-environment setup verification is complete. Production questions can
use an OpenAI-compatible tool-call protocol over the synchronous or SSE message
path to query the fictional AOI dataset, calculate a deterministic production
summary, and pass that evidence back to the model for the final answer. General
questions use the same SSE transport without manufacturing evidence.
Focused defect-distribution questions use a separate deterministic tool that
ranks recorded categories and reports each category's share of classified
defects.
The current v0.5 retrieval slice searches an explicit corpus of three
independently written fictional AOI documents: an alarm guide, an operator SOP,
and a preventive-maintenance guide. It uses deterministic local embeddings,
section-aware chunking, and a fixed lexical eligibility gate. Synchronous and SSE
answers can expose the matched excerpts and stable citation metadata in the
current assistant exchange.

The workbench now uses Ant Design 6.5.1, Ant Design X 2.9.0, and XMarkdown
2.9.0. Its dark-first responsive layout separates conversation navigation,
the message stream, and editable analysis context without adding unsupported
manufacturing dashboards or charts.

See the [implementation status](docs/implementation-status.md) for the
code-backed feature matrix and the [roadmap](docs/roadmap.md) for milestone
boundaries.

## What is implemented

- conversation create, list, open, and permanent delete;
- chronological user and assistant message persistence;
- synchronous and SSE assistant-response endpoints;
- typed LangGraph state and execution boundaries used by synchronous and SSE
  flows;
- conversation history passed to the configured model for continued dialogue;
- conversation-bound device, lot, time-range, environment, and data-source
  context;
- a deterministic catalog of three fictional devices for context selection;
- immutable manufacturing records and one reproducible fictional AOI dataset;
- deterministic yield, defect, and overlapping-alarm aggregation;
- a typed `get_production_summary` tool connected to synchronous and SSE
  production-question workflows;
- a typed `get_equipment_status` tool that reads explicit synthetic state
  intervals without inferring status from yield or alarms;
- a typed `get_defect_distribution` tool that ranks recorded defect categories
  without adding causal interpretation;
- a typed `search_documents` tool backed by heading-aware Markdown chunks, a
  deterministic feature-hashing embedding, an in-memory cosine index, and an
  explicit three-document registry;
- API-process health reporting;
- grouped conversation navigation with desktop and mobile Drawers;
- loading, empty, unavailable, streaming, cancellation, and reload states; and
- a dark Ant Design X workbench with responsive context editing, Markdown
  assistant responses, and restrained Dithered accents.

The browser uses SSE for general and supported manufacturing questions. Tool requests
emit tool-call and tool-result events, and the current exchange can display a
deterministic Production Summary result surface below the assistant answer,
including Defect Counts and Alarm Events, a recorded Equipment Status card, or
a ranked Defect Distribution card, or fictional document Sources.
Supported
saved workspace presets can fill missing device, lot, and time-range arguments.
Custom or unrecognized time ranges still require explicit UTC timestamps.

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
├── data/          # Independently created synthetic manufacturing data
├── docs/          # Scope, implementation status, and roadmap
└── scripts/       # Added only when project automation is needed
```

LangGraph and the first manufacturing-domain and production-tool slices are
implemented. Self-built RAG remains experimental; MCP remains
planned for a later milestone.

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

From `apps/web`, using a currently supported Node.js environment:

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
[implementation status](docs/implementation-status.md). The recorded clean
copy verification uses the committed lockfiles and migration workflow.

## Documentation

- [Documentation index](docs/README.md)
- [Project scope and publication boundaries](docs/project-scope.md)
- [Implementation status and API matrix](docs/implementation-status.md)
- [Milestone roadmap](docs/roadmap.md)

## Known limitations

- Health reports API-process availability only. It does not check the database,
  model service, or production tool.
- The configured model receives conversation history. Supported manufacturing
  tool requests also receive saved workspace context for missing arguments;
  general model requests do not receive that metadata.
- A failed assistant request leaves the user message persisted.
- Streaming depends on provider and proxy flushing behavior. The service
  creates an assistant record only after consuming a complete non-empty stream;
  client-disconnect persistence behavior still needs an integration test.
- Context values, device identities, and production records are synthetic.
  They do not represent live equipment or production state.
- Production tool calling requires a compatible model and still uses a small
  English keyword heuristic. Both synchronous and SSE production paths can
  execute the tool; after a successful SSE tool result, the final model answer
  is forwarded as provider token deltas.
- Structured evidence is available for the current exchange but is not
  persisted with Message history.
- Document retrieval currently covers three repository-owned fictional
  Markdown documents and a 12-scenario deterministic relevance fixture. It has
  no PDF/OCR ingestion, external embeddings, persistent vector store,
  reranking, or full-document viewer.
- There is no authentication, retry orchestration, or deployment stack.
- Conversation and message history are not paginated.

## License

No license has been selected. Until a license file is added, reuse rights are
not granted.
