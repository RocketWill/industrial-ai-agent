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
and 2 are implemented; Slice 3 runtime persistence is **In Progress**. Slice 1
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
response persists `evidence_snapshot` as `NULL`. Focused tests also cover the
Production Summary SSE tool runner: the `tool_result` stage still has only the
user row, while the final `assistant_message` event carries the canonical
snapshot. An Equipment Status runtime test verifies that a recorded `unknown`
result still persists as an available `equipment_status` canonical snapshot,
without mapping it to missing or unavailable. A synchronous Combined
partial-failure test retains succeeded manufacturing and failed documents
(`error_code: TOOL_UNAVAILABLE`). These tests reuse shared `persist_response`;
no production code changed.

These changes do not yet provide end-to-end evidence persistence. The focused
synchronous seam is not the full Slice 3 atomic-persistence acceptance
boundary. Runtime acceptance for the remaining Defect Distribution
empty-result and Document Search source paths and the combined SSE path,
rollback, cancellation, and client disconnect remain open. The read adapter,
service/API wiring, historical reload responses and UI, and Model Working
Notes are not yet implemented.

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
