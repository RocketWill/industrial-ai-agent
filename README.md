# Industrial AI Agent for Semiconductor Manufacturing

An independently developed full-stack industrial AI agent portfolio project for
manufacturing scenarios. The project will use only synthetic production data,
fictional equipment documentation, and configurable external services.

## Current status

**In Progress — v0.1 conversation workflow**

The FastAPI application foundation, environment-based settings, process health
endpoint, and explicit SQLite/SQLAlchemy migration infrastructure are
implemented and verified. The backend can create, list, open, and permanently
delete Conversation records, store user Messages, and reload each
Conversation's history in chronological order. It also includes a standalone
OpenAI-compatible chat adapter with a local Ollama default configuration.

The Message API now uses the adapter to generate and persist one assistant
response for each successful user message. The React application now provides
the health foundation and conversation navigation: it can load, create, select,
and delete conversations through the local development proxy. It can also load
persisted message history and submit synchronous user messages for complete
assistant responses. It also supports SSE streaming for incremental assistant
rendering and complete-response persistence.

## Project goals

The long-term goal is to demonstrate a traceable and testable industrial AI
agent that can:

- maintain conversation and manufacturing context;
- retrieve fictional equipment knowledge;
- invoke deterministic production analytics;
- distinguish retrieved, calculated, and inferred evidence;
- expose workflow events, tool calls, sources, errors, and retries; and
- evaluate behavior against reproducible synthetic scenarios.

See [project scope](docs/project-scope.md) for explicit boundaries and
[roadmap](docs/roadmap.md) for milestone status.

## Repository layout

```text
industrial-ai-agent/
├── apps/
│   ├── api/       # FastAPI backend with Conversation and Message persistence
│   └── web/       # React + TypeScript conversation foundation for v0.1
├── data/          # Synthetic project-owned data (not added yet)
├── docs/          # Scope, roadmap, architecture, and engineering notes
└── scripts/       # Project automation added only when needed
```

Directories for LangGraph, RAG, MCP, and manufacturing-domain features will be
introduced only in the milestone that implements them.

## Dependency management

The backend uses uv and a `pyproject.toml` inside `apps/api`, with dependency
groups for runtime and development packages. Its committed lockfile keeps the
environment reproducible, while Python environments remain local and are not
committed.

The frontend will use npm with a committed lockfile inside `apps/web`. Keeping
Python and Node project metadata beside their respective applications makes
each app independently testable without introducing a monorepo orchestrator
before one is needed.

## v0.1 acceptance criteria

v0.1 is complete only when all of the following are demonstrated:

- documented steps can start both applications in a clean environment;
- a user can create, list, open, and delete a conversation;
- a user can send a message and receive an assistant response;
- messages persist in SQLite and history reloads correctly;
- an OpenAI-compatible adapter is configurable without committing secrets;
- missing LLM configuration produces an explicit error or documented
  development fallback;
- backend API and persistence tests pass;
- critical frontend conversation interactions are covered by tests;
- frontend and backend failures are presented clearly; and
- documentation describes only behavior verified by code or tests.

LangGraph, RAG, MCP, production tools, industrial datasets, authentication,
streaming, Redis, and container deployment are outside v0.1.

Streaming is implemented as a separate v0.1.1 flow after the synchronous React
conversation workflow. The browser uses a POST request with SSE framing and an
AbortController; cancellation, disconnects, malformed streams, and empty
responses do not create partial assistant records.

The React shell now uses the Dithered dark UI foundation: shared Ant Design
theme tokens, a wider responsive workspace, and semantic dark surfaces. This
changes presentation only and does not change conversation or backend behavior.

The frontend now uses an Agent workbench information architecture: a two-column
navigation/workspace shell, explicit `Synthetic Demo Data` context, and shared
spacing and layout tokens. Future tool execution, manufacturing analytics, and
source panels will be introduced only with their supporting backend contracts.

The current UI milestone is v0.1.2, an Industrial Chat Workspace UI pass. Its
single-scroll shell, message widths, header/sidebar emphasis, and truthful
context bar are implemented and browser-verified. A later Slice B will add
industrial content surfaces only when backend contracts exist.

The next UI feature after v0.1.2 is an Industrial Context Layer for device, lot,
time range, data source, and agent capability context. It will use verified
values and will not create synthetic production results to fill the interface.

The first context contract slice is available per conversation through typed
GET/PATCH endpoints. The current UI reads and edits optional device, lot, and
time-range values without presenting unsupported production controls.

The device selector uses a deterministic fictional catalog from `GET /devices`.
It exposes identity metadata only and does not imply live equipment status.

The pre-LangGraph UI includes time-range presets, lot validation, and a
scroll-to-bottom affordance for long conversations. Desktop and mobile browser
checks confirm that only the conversation viewport scrolls.

## Development

The backend can be installed, run, and verified from `apps/api`:

```bash
uv sync --locked
uv run uvicorn industrial_agent.main:app --host 127.0.0.1 --port 8000
uv run pytest
uv run ruff check .
uv build
```

The browser health foundation can be installed, run, and verified from
`apps/web`:

```bash
npm ci
npm run dev
npm test
npm run typecheck
npm run lint
npm run build
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000` by
default. See the [API guide](apps/api/README.md) and
[web guide](apps/web/README.md) for the implemented contracts and current
limits.

Copy `.env.example` to `.env` only when local application configuration is
introduced. Never commit `.env`, credentials, private endpoints, real
production data, or proprietary material.

## Known limitations

- Conversation records and both user and assistant Messages are persisted.
- A Message request calls the configured OpenAI-compatible adapter. If that
  service is unavailable, the user Message remains stored and the API returns
  a safe `503` error.
- The frontend reports API-process availability and supports conversation
  navigation, history, synchronous messaging, and streaming.
- Streaming depends on provider and proxy support for timely response flushing.
- The data directory contains documentation only; no synthetic dataset has
  been designed.

## License

No license has been selected yet. Until a license file is added, reuse rights
are not granted.
