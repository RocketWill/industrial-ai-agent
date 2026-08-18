# Project Scope

## Positioning

Industrial AI Agent for Semiconductor Manufacturing is an independent,
educational portfolio project. It explores how a stateful AI agent can combine
manufacturing-domain models, production-data tools, equipment-document
retrieval, and explicit workflow orchestration to answer traceable industrial
questions.

All equipment interfaces, documents, datasets, alarm codes, and evaluation
scenarios will be synthetic and created specifically for this repository.

## Ownership and public-release boundary

This project is not a company product or a sanitized copy of an existing
system. It must be independently explainable, executable, and publishable.

The repository must not contain or imply:

- employer, customer, or proprietary product identities;
- copied source code, Git history, screenshots, documents, or schemas;
- internal URLs, IP addresses, APIs, deployment architecture, or credentials;
- real equipment names, factory data, production records, or customer data; or
- unauthorized work product or confidential implementation details.

General software-engineering knowledge may inform the design, but every
artifact in this repository must be independently authored.

## Intended capabilities

The planned system will eventually:

1. persist conversations and structured equipment/time-range context;
2. query synthetic equipment and production records;
3. calculate yield, throughput, status, and defect metrics in deterministic
   Python code;
4. retrieve fictional manuals, SOPs, and alarm guides with citations;
5. route requests to document, production, or combined workflows;
6. validate evidence and handle missing data, timeouts, invalid formats, and
   retries safely;
7. display execution traces, tool calls, sources, errors, and retry activity;
   and
8. evaluate agent behavior with fixed synthetic scenarios.

## Evidence and answer boundaries

Responses must distinguish:

- document retrieval results;
- structured production records;
- programmatically calculated metrics;
- model-generated interpretation; and
- uncertainty or insufficient evidence.

The system must not invent equipment state, production values, yield, defects,
or causal explanations when evidence is absent. Numeric manufacturing logic
belongs in deterministic domain code rather than an LLM.

## Current milestone boundary

v2.0 Persistent Evidence and Model Working Notes is **In Progress**. Slices 1
through 6 are implemented. Slice 1
defines the version-1 typed
`MessageRead.evidence_snapshot` union for Production Summary, Equipment Status,
Defect Distribution, Document Search, Combined Evidence, and the explicit
Unavailable Evidence state. Slice 2 adds Alembic revision
`0006_add_evidence_snapshot` with nullable JSON `messages.evidence_snapshot`,
synchronizes the Message ORM model, keeps existing messages readable with
`NULL` after upgrade, and passes downgrade compatibility tests. Slice 3 adds a
narrow conversion and message-service boundary. `current_evidence_to_snapshot` converts the four typed
single evidence outcomes and Combined Evidence outcomes, including partial
path results, into version-1 canonical snapshot JSON. The message service
validates explicitly supplied assistant Evidence Snapshot values, preserves
their JSON round-trip, rejects snapshots on user messages, and keeps omitted
assistant snapshots `NULL`. The synchronous workflow's `persist_response` now
passes the canonical snapshot through the same assistant-message commit path.
A focused Production Summary integration verifies that path; a general
response persists `evidence_snapshot` as `NULL`. Slice 3 runtime persistence
covers the four single-evidence paths, including complete Document Search
sources, and Combined success/failure/empty cases with matching synchronous and
SSE behavior and bounded fallback. Snapshot-construction failure retains the
user row without an assistant row or snapshot. An assistant insert failure
rolls back, retains the user row, and leaves the session usable. Cancellation
and a real-socket client disconnect leave no assistant row or snapshot. The
runtime suite reports 99 passed; Ruff and `git diff --check` passed.

Slice 4 is implemented across the backend and frontend. The completed
`MessageExchangeRead` contract contains only `user_message` and
`assistant_message`; canonical evidence appears only at
`assistant_message.evidence_snapshot`; synchronous completion and `GET`
history return matching snapshots; legacy top-level `evidence` and
`combined_evidence` fields are removed; and current SSE tool events remain
available. The frontend strictly validates five available snapshot kinds,
explicit unavailable states, and missing snapshots; keeps evidence on the
assistant message across history reload; clears current evidence on SSE
completion after applying the returned persisted assistant; and renders
historical snapshots with a label and message capture time by reusing the
existing evidence panels. An unavailable snapshot keeps the assistant message
visible. Slice 4 focused verification reports 69 frontend and 41 backend
tests; the full Web suite reports 127 passed, with TypeScript checking and the
production build passing. ESLint completed with the existing
`react-refresh/only-export-components` warning. Ant Design CLI `info`, `lint`, `doctor`, and
`bug-cli` were blocked by the existing missing
`@oxc-parser/binding-darwin-arm64` optional native package. No browser
acceptance was run for this slice; the existing Vite chunk-size warning is
retained.

Slice 5 is implemented at the provider-adapter boundary. Final-answer stream
normalization emits separate internal reasoning items for explicit provider
`reasoning_content` deltas and literal lowercase, non-nesting
`<think>...</think>` wrappers. It handles arbitrary tag chunk splits, multiple
wrappers, answer text around wrappers, unclosed wrappers, and reasoning-only
responses while preserving the existing empty-response behavior. A fixed
16,000-Unicode-character cap emits one truncation item, discards further
reasoning, and continues consuming the final-answer stream. Synchronous general
and post-tool final answers strip recognized wrapper reasoning; initial tool
selection, default stream behavior, and providers without reasoning remain
unchanged. Slice 5 focused verification reports 51 passed; the full API suite
reports 459 passed, with Ruff and `git diff --check` passing. Slice 5 itself
did not expose Model Working Notes through SSE or the frontend.

Slice 6 is implemented for final-answer streams. Final-answer calls opt into
the internal `StreamItem` union; the runner emits the approved
`reasoning_delta` and `reasoning_truncated` SSE events while persisting only
the Final Answer. The frontend validates those events, keeps reasoning in
ephemeral hook state, and renders it with a native plain-text disclosure. The
disclosure opens on the first reasoning delta, closes when the first answer
token arrives, supports manual reopening, represents truncation and
interruption, clears on reload or conversation switch, excludes notes from
copy actions, avoids per-delta `aria-live` announcements, and bounds rendered
overflow. Synchronous responses and routing or tool-selection streams do not
expose working notes; the tool-selection text fallback strips recognized
reasoning wrappers. Slice 6 focused verification reports 89 backend and 86
frontend tests; the full API suite reports 463 passed and the full Web suite
reports 144 passed, with type checking, linting, builds, Ruff, and
`git diff --check` passing. The existing Ant Design CLI native-binding block
remains. Reproducible browser acceptance passed with an independent
OpenAI-compatible streaming fixture: the disclosure opened during reasoning,
closed on the first Final Answer token, reopened by pointer interaction, and
cleared on reload while the answer remained. At 390px there was no horizontal
page overflow; the reasoning body was bounded at 220px with overflow scrolling,
and the disclosure showed a visible focus outline. This does not claim a live
Qwen reasoning pass; its routing delay was excluded from deterministic UI
acceptance. The browser run upgraded the local Alembic database from `0005` to
`0006` without deleting data.

The following v2.0 work remains:

- Slice 7 — Final v2.0 acceptance.

v1.0 Portfolio Release is **Implemented**. It packages the verified v0.9
application as a repository-only release. Corrective validation and responsive
layout changes found by release verification are allowed, but new workflows,
tools, or public contracts remain outside this milestone.
The release boundary passed local deterministic verification, Combined
Evidence browser acceptance, public-copy and publication review, two-axis code
review, and remote CI on 2026-08-15.

The latest completed milestone is **v1.0 — Portfolio Release**. Its packaged
application includes the **v0.9 — Combined Evidence Workflow**, which
executes one manufacturing evidence path followed by Document Search in a
single current exchange, with independent path states and bounded query
enrichment. The v0.1 foundation,
v0.1.1 streaming extension, v0.1.2 workspace extension, and v0.2 minimal
LangGraph orchestration are implemented, including clean-environment
verification. v0.3 Manufacturing Domain is implemented; throughput is
explicitly deferred until a later dataset and unit contract can support it. Its
domain slices provide deterministic production summaries and defect
distributions, explicit equipment-state
intervals, point-in-time status lookup, and one fictional AOI wafer-inspection
dataset.

The current backend includes explicit SQLite migrations, Conversation and
Message persistence, synchronous and streaming OpenAI-compatible chat flows,
conversation-bound workspace context, a deterministic fictional device
catalog, and synchronous plus SSE production-summary, defect-distribution, and
equipment-status tool flows. The current document slice builds an explicit
three-document fictional Markdown corpus and exposes deterministic local
retrieval through synchronous and SSE `search_documents` flows. The React
application provides API-process health, conversation and message workflows,
streaming controls, responsive conversation navigation, draft-based context
editing, Markdown assistant rendering, and current-exchange tool stages and
evidence for routed production-summary, defect-distribution, equipment-status,
and fictional document requests.

The MCP entrypoint independently exposes production summary, recorded
equipment status, and defect distribution over local stdio. It reuses the
native deterministic tool contracts and synthetic dataset without adding MCP
to FastAPI, LangGraph, or the frontend. HTTP transport, authentication, remote
deployment, document search, and live manufacturing access remain outside the
v0.7 boundary.

The evaluation entrypoint runs 45 fixed English and Traditional Chinese
scenarios through existing routing, tool, retrieval, evidence, and answer
validation seams. It records per-dimension assertions and local stage timing
in an ignored JSON artifact. The command does not add an LLM judge, provider
call, HTTP endpoint, frontend panel, persisted application trace, composite
score, or latency gate.

Streaming and the refined workspace are recorded as completed v0.1.1 and
v0.1.2 extensions.

The following are deliberately excluded from v0.1:

- LangGraph orchestration;
- manufacturing domain models and datasets;
- production-data tools;
- RAG and vector storage;
- MCP;
- authentication, multi-tenancy, and complex authorization;
- Redis, microservices, and high-availability deployment; and
- Docker or cluster infrastructure.

Streaming is outside the original v0.1 contract but implemented in v0.1.1.
Keeping it separate allowed client cancellation, partial-response handling,
and the completed-response persistence boundary to be specified together.

The completed v0.5 milestone includes stable
section-local citations, bounded paragraph- and list-aware chunks,
deterministic feature-hashing embeddings, an in-memory cosine index, a fixed
lexical eligibility gate, and a 12-scenario retrieval fixture. It uses no
external embedding service. A registry-only API and read-only Drawer expose
the complete cited document. Local Markdown management adds persistent,
Git-ignored single-file uploads, validation, atomic corpus replacement, and
deletion while protecting built-ins. Multi-tool turns, PDF/OCR, authentication,
cloud storage, and persisted evidence remain outside the current boundary.

The completed v0.6 milestone adds typed English and Traditional Chinese routing,
bounded classifier retry and fallback, deterministic clarification, shared
synchronous and SSE decisions, evidence sufficiency checks, and safe routing
progress events. Combined execution was added later in v0.9; routing traces are
still not persisted.

The completed v0.6.1 milestone adds two persisted, application-owned actions to
the combined clarification. Selecting one records a normal user message and
reuses the existing routing workflow. It does not add multi-tool execution,
context selectors, model-generated actions, or a special execution endpoint.
Those historical choices remain supported; explicit new combined requests now
use the v0.9 workflow.

## Publication safety

Only placeholder configuration and synthetic artifacts may be committed.
Secrets belong in ignored local environment files. If the provenance or public
safety of an artifact is uncertain, it must remain outside the repository
until reviewed.

## Status vocabulary

Project documentation uses these labels:

- **Implemented** — supported by working code and relevant verification
- **Experimental** — working exploration without a stable contract
- **In Progress** — actively being built and not yet accepted
- **Planned** — not implemented
- **Deprecated** — retained temporarily but no longer recommended
