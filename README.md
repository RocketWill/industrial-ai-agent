# Industrial AI Agent for Semiconductor Manufacturing

An independently developed full-stack industrial AI agent portfolio project for
manufacturing scenarios. The project will use only synthetic production data,
fictional equipment documentation, and configurable external services.

## Current status

**In Progress — v0.1 repository baseline**

This repository currently contains project scope, roadmap, development
boundaries, and the minimal monorepo structure. The FastAPI service, React
application, database models, and LLM integration have not been implemented yet.

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
│   ├── api/       # FastAPI backend (planned for v0.1)
│   └── web/       # React + TypeScript frontend (planned for v0.1)
├── data/          # Synthetic project-owned data (not added yet)
├── docs/          # Scope, roadmap, architecture, and engineering notes
└── scripts/       # Project automation added only when needed
```

Directories for LangGraph, RAG, MCP, and manufacturing-domain features will be
introduced only in the milestone that implements them.

## Dependency management

The backend will use a `pyproject.toml` inside `apps/api`, with dependency groups
for runtime and development packages. Python environments remain local and are
not committed. The exact installer will be selected when the backend is
implemented; the committed project metadata will remain compatible with
standards-based Python tooling.

The frontend will use npm with a committed lockfile inside `apps/web`. Keeping
Python and Node project metadata beside their respective applications makes
each app independently testable without introducing a monorepo orchestrator
before one is needed.

No application dependencies are installed in this baseline.

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

Implementation setup commands will be added with the first FastAPI and React
changes. Until then, this baseline has no build or test command.

Copy `.env.example` to `.env` only when local application configuration is
introduced. Never commit `.env`, credentials, private endpoints, real
production data, or proprietary material.

## Known limitations

- There is no runnable application yet.
- No dependencies or automated tests exist yet.
- The data directory contains documentation only; no synthetic dataset has
  been designed.

## License

No license has been selected yet. Until a license file is added, reuse rights
are not granted.
