# Roadmap

Milestones are completed only when their documented behavior is runnable,
tested, demonstrable, and accurately described. Planned items are not
implemented features.

## v0.1 — Full-stack Foundation

**Status: In Progress**

Current baseline:

- [x] Define independent project scope and publication boundaries.
- [x] Document milestone roadmap and v0.1 acceptance criteria.
- [x] Establish minimal `apps/api` and `apps/web` boundaries.
- [x] Add safe ignore rules and configuration placeholders.
- [x] Create the FastAPI application and health endpoint.
- [x] Add settings, SQLite, SQLAlchemy, and schema migrations.
- [x] Implement conversation management and append-only message persistence.
- [x] Add one OpenAI-compatible chat adapter.
- [x] Create the React, TypeScript, and Vite application.
- [x] Implement and test frontend API-process health connection states.
- [x] Connect the frontend conversation navigation to the existing API.
- [x] Connect frontend message history and synchronous assistant responses.
- [x] Implement persisted message interactions and assistant responses.
- [x] Connect frontend and backend with clear error states.
- [x] Add backend API, persistence, migration, and adapter tests.
- [x] Add critical frontend conversation interaction tests.
- [ ] Document clean-environment setup and verified limitations.
- [x] Apply the Dithered dark UI foundation, shared Ant Design theme tokens,
      and responsive conversation workspace layout.

Acceptance criteria are defined in the root README. This milestone explicitly
excludes LangGraph, RAG, MCP, manufacturing data/tools, authentication,
streaming, Redis, and deployment infrastructure.

## v0.1.1 — Streaming Conversation

**Status: Planned**

Add streaming only after the synchronous React conversation workflow is
implemented and verified. Define one browser-compatible streaming transport,
incremental assistant rendering, cancellation and disconnect behavior, safe
error reporting, and the persistence rule for complete or interrupted
assistant responses. Cover these boundaries with focused backend and frontend
tests before describing streaming as implemented.

This milestone does not add LangGraph, tool calling, retries, manufacturing
logic, RAG, or execution traces.

## v0.2 — Minimal LangGraph

**Status: Planned**

Replace or wrap direct chat orchestration with a minimal graph containing
context loading, an LLM node, response persistence, execution events, and
state-transition tests.

## v0.3 — Manufacturing Domain

**Status: Planned**

Define synthetic equipment, production, inspection, defect, yield, alarm,
time-range, and status models. Specify numeric semantics and boundary behavior,
then verify them with deterministic unit tests.

## v0.4 — Production Data Tools

**Status: Planned**

Implement a small set of schema-driven tools for equipment status, yield
summary, and defect distribution. Keep domain logic independent of LangGraph
and preserve tool evidence for display.

## v0.5 — Self-built RAG

**Status: Planned**

Add ingestion, parsing, chunking, embedding, vector storage, retrieval,
citations, source viewing, and retrieval tests using fictional manuals, SOPs,
and alarm guides.

## v0.6 — Routing and Reliability

**Status: Planned**

Add structured intent/context extraction, conditional document/production/
combined routing, evidence validation, timeouts, retries, empty-result
handling, clarification, safe failure, and observable traces.

## v0.7 — MCP

**Status: Planned**

Expose selected stable tools through MCP while retaining native Python
adapters. Compare contracts, latency, errors, boundaries, and test complexity
without moving domain logic into transport handlers.

## v0.8 — Evaluation and Observability

**Status: Planned**

Measure tool selection, retrieval relevance, answer grounding, citation
correctness, failure recovery, latency, retries, and unsupported claims against
a fixed synthetic scenario set.

## v1.0 — Portfolio Release

**Status: Planned**

Publish reproducible setup, verified architecture documentation, demo
scenarios, screenshots, evaluation results, known limitations, security review,
and a clean public repository.
