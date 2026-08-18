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
logic, RAG, or execution traces. A later real-socket integration test verifies
that a client disconnect before completion does not persist a partial assistant
message; provider-side generation cancellation is not guaranteed.

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

**Status: Implemented**

Add structured intent and context extraction, conditional document,
production, and combined routing, evidence validation, timeouts, retries,
empty-result handling, clarification, safe failure, and observable traces.

Implemented slices:

- [x] Add immutable routing candidates and decisions plus a 38-scenario
  English and Traditional Chinese fixture.
- [x] Add a deterministic gate and typed `classify_request` adapter with a
  1–30 second timeout and one bounded retry.
- [x] Add one authoritative policy with context precedence, clarification,
  unsupported responses, conservative fallback, and safe routing logs.
- [x] Validate route-specific evidence and reject ungrounded numeric or
  uncited document answers deterministically.
- [x] Use the shared policy in synchronous and SSE workflows.
- [x] Expose bounded routing progress without adding a persistent trace
  timeline.

At the v0.6 boundary, combined requests remained clarification-only.
Evidence-tool retries, persisted
routing traces, and broader multilingual support remain outside this milestone.

## v0.6.1 — Guided Routing Choices

**Status: Implemented**

Persist two application-owned choices with a combined-route clarification:
`Production evidence` and `Document evidence`. The latest unresolved
clarification remains actionable after reload, and selecting one choice sends a
normal user message through the existing SSE and routing workflow.

Implemented slices:

- [x] Add a typed persisted `suggested_actions` message contract and one
  explicit migration.
- [x] Attach the two fixed actions only to combined-route clarifications in
  synchronous and SSE paths.
- [x] Render the latest unresolved actions with accessible one-shot submission,
  loading, disabled, reload, and failure behavior.
- [x] Complete browser acceptance, two-axis review, verification, and public
  documentation updates before starting v0.7.

This milestone does not execute combined tools, add equipment or time-range
choices, accept model-generated actions, or introduce a special action API.

## v0.7 — MCP

**Status: Implemented**

Expose selected stable tools through MCP while retaining native Python
adapters. Compare contracts, latency, errors, boundaries, and test complexity
without moving domain logic into transport handlers.

Implemented slices:

- [x] Add the official Python MCP SDK and an independent local stdio
  entrypoint.
- [x] Expose `get_production_summary` with strict input validation, structured
  output, deterministic text fallback, and native-result parity tests.
- [x] Verify discovery, calls, errors, startup, and clean shutdown through an
  official MCP stdio client.
- [x] Expose `get_equipment_status` while preserving recorded `unknown`
  evidence and native-result parity.
- [x] Expose `get_defect_distribution` while preserving empty evidence,
  limitations, and native-result parity.

This milestone does not add MCP to FastAPI, LangGraph, or the frontend. It also
excludes HTTP transport, authentication, remote deployment, document search,
client-side workspace-context resolution, and live manufacturing data.

## v0.8 — Evaluation and Observability

**Status: Implemented**

Measure tool selection, retrieval relevance, answer grounding, citation
correctness, failure recovery, latency, retries, and unsupported claims against
a fixed synthetic scenario set.

Implemented slices:

- [x] Define one strict, package-owned 30-scenario English and Traditional
  Chinese fixture, including the existing 12 retrieval cases.
- [x] Execute routing, retry, fallback, native manufacturing tools, document
  retrieval, evidence checks, and answer validation through existing seams.
- [x] Keep route, tool, argument, evidence, retrieval, citation, safe-failure,
  unsupported-claim, and retry outcomes as separate dimensions.
- [x] Add `industrial-agent-eval`, filtered runs, exact exit behavior, and an
  ignored typed JSON artifact with fixture digest and monotonic stage timing.
- [x] Verify all formal thresholds without an LLM judge, external telemetry,
  persisted application traces, a composite score, or a latency gate.

## v0.9 — Combined Evidence Workflow

**Status: Implemented**

Execute one bounded manufacturing evidence path followed by Document Search in
a single assistant exchange. The manufacturing result may enrich retrieval
with explicit recorded fields, while the answer keeps numeric manufacturing
claims, document citations, limitations, and possible relationships separate.

Implemented slices:

- [x] Route explicit combined requests to exactly one Production Summary,
  Equipment Status, or Defect Distribution path plus Document Search.
- [x] Execute manufacturing first and enrich the document query only with
  allowlisted recorded fields.
- [x] Preserve independent succeeded, empty, failed, and current-exchange-only
  path states across synchronous and ordered SSE contracts.
- [x] Keep available evidence when one path or answer generation fails, without
  inventing missing results, citations, or causal conclusions.
- [x] Render one responsive assistant exchange with separate manufacturing and
  document regions, including loading and failure semantics.
- [x] Extend the deterministic bilingual suite to 45 scenarios covering the
  combined pairings, clarification, partial and double failure, empty evidence,
  citations, numeric grounding, and causal-claim rejection.

This milestone does not add a planner, multiple manufacturing tools in one
turn, persisted evidence history, evidence-tool retries, or causal analysis.

## v1.0 — Portfolio Release

**Status: Implemented**

Publish reproducible setup, verified architecture documentation, demo
scenarios, screenshots, evaluation results, known limitations, security review,
and a clean public repository.

## v2.0 — Persistent Evidence and Model Working Notes

**Status: In Progress**

Open the v2.0 boundary while keeping v1.0 Implemented. Slice 1 adds a
version-1 typed `MessageRead.evidence_snapshot` union for Production Summary,
Equipment Status, Defect Distribution, Document Search, Combined Evidence, and
the explicit Unavailable Evidence state. Slice 2 adds the nullable JSON storage
boundary for that field. Slice 3 adds a narrow conversion and message-service
write boundary: `current_evidence_to_snapshot` converts the four typed single
evidence outcomes and Combined Evidence outcomes, including partial path
results, into version-1 canonical snapshot JSON. `create_message` validates an
assistant Evidence Snapshot, stores its canonical JSON representation, preserves
the JSON round-trip on reads, rejects snapshots on user messages, and leaves an
omitted assistant snapshot as `NULL`.

Implemented slices:

- [x] Define and validate the version-1 Evidence Snapshot read union at the
  message schema boundary.
- [x] Add Alembic revision `0006_add_evidence_snapshot` with nullable JSON
  `messages.evidence_snapshot`, synchronize the Message ORM model, preserve
  existing messages as readable rows with `NULL` after upgrade, and verify
  downgrade compatibility.
- [x] Convert Production Summary, Equipment Status, Defect Distribution,
  Document Search, and Combined Evidence current outcomes into version-1
  canonical snapshots, retaining per-path partial outcomes.
- [x] Validate and JSON-round-trip an explicitly supplied assistant Evidence
  Snapshot in the message service, reject snapshots on user messages, and
  preserve `NULL` when an assistant snapshot is omitted.
- [x] Verify Slice 3 runtime persistence across the four single-evidence paths,
  Combined success/failure/empty cases, synchronous/SSE parity, rollback, and
  cancellation or client-disconnect boundaries.
- [x] Complete the frontend Evidence Snapshot boundary: strictly validate five
  available kinds, explicit unavailable states, and missing snapshots; keep
  snapshots on assistant messages across history reload; clear current
  evidence on SSE completion after applying the returned persisted assistant;
  and render historical snapshots with a label and message capture time using
  the existing evidence panels while keeping the assistant message visible
  when evidence is unavailable.
- [x] Normalize explicit provider reasoning and literal `<think>` wrappers into
  bounded internal stream items without contaminating Final Answer content.
- [x] Expose bounded final-answer reasoning through ephemeral SSE and frontend
  state without persisting Model Working Notes or exposing them on synchronous,
  routing, or tool-selection responses.

The schema, conversion, message-service, and runtime-persistence boundaries
above are implemented. Slice 3 persists canonical snapshots for the four
single-evidence paths: Production Summary, Equipment Status, Defect
Distribution, and Document Search with complete sources. Combined success,
one-path failure, double failure, and empty-result cases retain per-path
status/result data with matching synchronous and SSE behavior; model failure
uses the bounded fallback. General responses persist `evidence_snapshot` as
`NULL`.

Snapshot-construction failure leaves the user row without an assistant row or
snapshot. An assistant insert failure rolls back the insert, retains the user
row, and leaves the session usable. Cancellation and a real-socket client
disconnect likewise leave no assistant row or snapshot. The Slice 3 runtime
suite reports 99 passed; Ruff and `git diff --check` passed.

Slice 4 is implemented across the backend and frontend. Completed
`MessageExchangeRead` responses contain only `user_message` and
`assistant_message`; canonical evidence appears only at
`assistant_message.evidence_snapshot`; synchronous completion and `GET`
history return matching snapshots; legacy top-level `evidence` and
`combined_evidence` fields are removed; and current SSE tool events remain
available. The frontend strictly validates five available snapshot kinds,
explicit unavailable states, and missing snapshots; keeps snapshots on the
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

The following v2.0 slices remain open:

- [ ] Slice 7 — Complete final v2.0 acceptance.
