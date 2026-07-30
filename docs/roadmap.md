# Roadmap

Milestones are accepted only when their documented behavior is runnable,
tested, demonstrable, and accurately described. Detailed implemented behavior
is tracked in [implementation status](implementation-status.md).

## v0.1 — Full-stack Foundation

**Status: Implemented**

Implemented:

- [x] Define independent project scope and publication boundaries.
- [x] Establish `apps/api` and `apps/web` application boundaries.
- [x] Add the FastAPI process-health endpoint and environment settings.
- [x] Add SQLite, SQLAlchemy, foreign-key enforcement, and Alembic migrations.
- [x] Implement conversation management and append-only message persistence.
- [x] Add one configurable OpenAI-compatible chat adapter.
- [x] Implement the React conversation workflow and explicit failure states.
- [x] Add focused backend and frontend tests.
- [x] Document local setup, configuration, contracts, and known limitations.

The clean-environment workflow was verified from a committed git archive copy:
dependencies installed from both lockfiles, migrations reached head, and the
API and Web test suites passed.

This milestone excludes LangGraph, RAG, MCP, manufacturing datasets and tools,
authentication, distributed infrastructure, and deployment orchestration.
Streaming remains a separate v0.1.1 extension.

## v0.1.1 — Streaming Conversation

**Status: Implemented**

The browser and API use one SSE transport for incremental assistant rendering.
The browser can cancel its request, malformed responses produce safe errors,
and the service persists an assistant message only after it consumes a
non-empty completed response. Backend and frontend tests cover event parsing,
error handling, and the completed-response persistence boundary.

This milestone does not add LangGraph, tool calling, retries, manufacturing
logic, RAG, or execution traces. Client-disconnect persistence still needs a
dedicated integration test.

## v0.1.2 — Industrial Chat Workspace UI

**Status: Implemented**

The React application now provides:

- a restrained Dithered theme configured through shared Ant Design tokens;
- desktop sidebar navigation and a mobile Drawer;
- a viewport-bound application shell with fixed header and composer;
- a single primary scrollbar for the conversation viewport;
- readable user and assistant message widths;
- assistant reasoning-tag suppression, copy actions, loading and empty states;
- conversation-bound context display and editing;
- a deterministic fictional device selector;
- time-range presets, lot validation, and scroll-to-bottom behavior; and
- explicit Synthetic Demo labeling.

Desktop and mobile browser checks confirm the shell and overflow hierarchy.
The original v0.1.2 interface did not provide tool activity, metric summaries,
sources, manufacturing charts, live equipment values, or production-backed
analysis. The current workbench adds only the tool stages and structured
evidence supported by the later v0.4 contracts.

## v0.2 — Minimal LangGraph

**Status: Implemented**

The synchronous Message API executes a compiled typed graph with context
loading, model execution, safe errors, and completed assistant persistence. The
SSE runner reuses the same typed state plus the context-loading and persistence
steps, while emitting model token events directly instead of invoking the
compiled graph. Workspace Context remains synthetic metadata and is not
converted into a system prompt. Graph, API regression, and frontend
compatibility tests pass.

This milestone does not add tool nodes, manufacturing analytics, RAG, MCP,
retry orchestration, or workflow visualization.

### v0.2 UI refinement

**Status: Implemented**

The existing workbench was refined without changing its routes or API
contracts. The sidebar now exposes only the available analysis workspace, the
workspace header and synthetic context have clearer hierarchy, the empty state
uses prompts that match the current conversation capability, and assistant
responses have a distinct analysis block treatment.

This refinement does not claim manufacturing analytics, source evidence, tool
activity, or evaluation views. Those remain tied to the later milestones that
implement their backend behavior.

### Responsive analysis workbench modernization

**Status: Implemented**

The frontend now uses Ant Design 6.5.1, Ant Design X 2.9.0, and XMarkdown
2.9.0. The desktop layout separates conversation navigation, the message
stream, and the analysis context inspector. Tablet and mobile layouts move the
secondary surfaces into focused Drawers. Conversations are grouped by recency,
context edits use an explicit draft and Save workflow, and assistant streaming,
tool stages, Markdown, and current-exchange evidence share one message surface.

This modernization does not add routes, manufacturing charts, persistent
evidence, arbitrary UTC time entry, RAG sources, attachments, or a complete
tool execution timeline. Those capabilities still depend on later contracts.

## v0.3 — Manufacturing Domain

**Status: Implemented**

Define synthetic equipment, production, inspection, defect, yield, alarm,
time-range, and status models. Specify numeric semantics and boundary behavior,
then verify them with deterministic unit tests.

Implemented slices:

- [x] Define the shared manufacturing-analysis language.
- [x] Add UTC Time Range, Equipment, Production Lot, Inspection Record, Defect
  Count, Alarm Event, Yield Rate, and Production Summary semantics.
- [x] Enforce inspection-count conservation and defect-count boundaries.
- [x] Aggregate yield, defects, and overlapping alarms deterministically.
- [x] Add a reproducible fictional AOI wafer-inspection dataset without a
  causal claim.
- [x] Define explicit UTC equipment-state intervals and deterministic
  point-in-time lookup with an `unknown` result when no state is recorded.

Throughput is deferred until a later milestone defines a dataset and unit
contract that can support it. It is not implied by inspection counts or the
current time-window summaries.

## v0.4 — Production Data Tools

**Status: Implemented**

Implement a small set of schema-driven tools for equipment status, yield
summary, and defect distribution. Keep domain logic independent of LangGraph
and preserve tool evidence for display.

Implemented slices:

- [x] Add typed `get_production_summary` request and result contracts.
- [x] Filter the synthetic AOI dataset by Equipment, Time Range, and optional
  Production Lot.
- [x] Preserve deterministic Yield Rate, Defect Counts, Alarm Events, and
  explicit empty-result limitations.
- [x] Add an OpenAI-compatible single-tool-call request and response protocol.
- [x] Integrate the production summary tool with the synchronous LangGraph
  workflow and return a model-written answer grounded in tool evidence.
- [x] Route a focused English production-query keyword set through the
  supported synchronous and SSE production execution paths.
- [x] Resolve explicit tool arguments and saved synthetic workspace context
  into complete production-tool arguments, with clarification when required
  values are missing.
- [x] Expose optional synchronous production evidence through the message
  contract and render a compact frontend summary card.
- [x] Add an SSE production tool event contract for tool call, result, final
  text, and completion events.
- [x] Stream model tokens during the SSE production tool path after a
  successful tool result.
- [x] Add a focused UI result surface for the current Production Summary,
  Defect Counts, Alarm Events, provenance, and empty states.
- [x] Add a typed `get_equipment_status` contract backed only by explicit
  synthetic state intervals.
- [x] Resolve a missing status timestamp from the saved Workspace Context end,
  execute the tool through synchronous and SSE flows, and return `unknown`
  when no recorded interval covers the timestamp.
- [x] Render current-exchange Equipment Status evidence with effective
  boundaries, reason code, provenance, and limitations.
- [x] Add a typed `get_defect_distribution` contract that ranks recorded
  categories and reports shares against classified defect counts.
- [x] Route focused defect-distribution questions through synchronous and SSE
  execution before the broader production-summary route.
- [x] Render current-exchange Defect Distribution evidence with counts, ranks,
  shares, provenance, empty states, and explicit limitations.

The milestone excludes throughput, trend analysis, causal diagnosis,
multi-tool turns, and persisted evidence history.

## v0.5 — Self-built RAG

**Status: Implemented**

Add ingestion, parsing, chunking, embedding, vector storage, retrieval,
citations, source viewing, and retrieval tests using fictional manuals, SOPs,
and alarm guides.

Implemented slices:

- [x] Add an explicit corpus of three independently written fictional AOI
  documents: an alarm guide, operator SOP, and preventive-maintenance guide.
- [x] Parse paragraph- and list-aware Markdown chunks inside H2/H3 section
  boundaries, with stable section-local citation identifiers.
- [x] Build deterministic feature-hashing embeddings and an in-memory cosine
  index without an external service or vector database.
- [x] Apply a fixed lexical eligibility gate before the global cosine threshold.
- [x] Add a typed `search_documents` tool to synchronous and SSE single-tool
  flows for focused English procedural questions.
- [x] Render current-exchange source title, section, excerpt, match score,
  repository-relative path, and Synthetic Demo provenance.
- [x] Cover parser, ranking, tool, workflow, SSE, runtime validation, and source
  rendering with focused tests.
- [x] Add a machine-readable 12-scenario retrieval fixture with repeatable
  top-one, top-three, confusable-query, and unrelated-query checks.

Planned remaining slices, in order:

- [x] Add a read-only full-document source viewer for repository-owned
  documents, with citation section positioning and retryable failure states.
- [x] Add local Markdown document management with a document list, single-file
  upload, validation, indexing status, atomic corpus replacement, and deletion
  for uploaded documents. Keep the three built-in documents protected.
- [x] Complete the v0.5 acceptance review and reconcile verified behavior with
  the public documentation.

The upload flow is a local development and portfolio feature, not a secure
multi-user document service. PDF/OCR, Word files, batch upload, authentication,
cloud storage, external vector infrastructure, and combined multi-tool turns
remain outside v0.5.

## v0.6 — Routing and Reliability

**Status: Planned**

Add structured intent and context extraction, conditional document,
production, and combined routing, evidence validation, timeouts, retries,
empty-result handling, clarification, safe failure, and observable traces.

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
