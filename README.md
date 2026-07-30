# Industrial AI Agent for Semiconductor Manufacturing

An independently developed full-stack industrial AI agent portfolio project for
manufacturing scenarios. The project will use only synthetic production data,
fictional equipment documentation, and configurable external services.

## Current status

**In Progress — v0.1 conversation workflow**

The FastAPI application foundation, environment-based settings, process health
endpoint, and explicit SQLite/SQLAlchemy migration infrastructure are
implemented and verified. The backend can now create, list, open, and
permanently delete Conversation records. It can also store user Messages and
reload each Conversation's history in chronological order. Assistant response
generation, the React application, and LLM integration have not been
implemented yet.

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
│   └── web/       # React + TypeScript frontend (planned for v0.1)
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

## Development

The backend can be installed, run, and verified from `apps/api`:

```bash
uv sync --locked
uv run uvicorn industrial_agent.main:app --host 127.0.0.1 --port 8000
uv run pytest
uv run ruff check .
uv build
```

See the [API guide](apps/api/README.md) for the implemented contract, explicit
Alembic migration commands, and current limitations. Frontend setup commands
will be added when that application is implemented.

Copy `.env.example` to `.env` only when local application configuration is
introduced. Never commit `.env`, credentials, private endpoints, real
production data, or proprietary material.

## Known limitations

- Conversation and user Message records are persisted, but assistant
  responses are not generated.
- LLM integration and the frontend remain planned.
- The data directory contains documentation only; no synthetic dataset has
  been designed.

## License

No license has been selected yet. Until a license file is added, reuse rights
are not granted.
