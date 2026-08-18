# Implementation Status

This document is the code-backed feature inventory for the repository. It was
reviewed against the application code, migrations, tests, and public
documentation on 2026-08-17. The latest recorded verification run remains
dated separately below.

## Status rules

- **Implemented** means working code exists and relevant automated or browser
  verification has been recorded.
- **In Progress** means part of the acceptance boundary remains open.
- **Planned** means no supported implementation exists.

The roadmap owns milestone status. This document owns the detailed feature
matrix. Application README files own setup and contract usage.

## Feature matrix

| Area | Status | Implemented behavior | Current boundary |
| --- | --- | --- | --- |
| API process health | Implemented | `GET /health` reports whether the FastAPI process responds. | It does not inspect SQLite, the LLM service, or future tools. |
| Database foundation | Implemented | SQLite, synchronous SQLAlchemy sessions, foreign-key enforcement, and six explicit Alembic revisions, including the nullable `messages.evidence_snapshot` column. | Application startup does not create or migrate schema. |
| Conversations | Implemented | Create, list newest first, open, and permanently delete conversations. | No rename, archive, restore, or pagination. |
| Message history | Implemented | Persist user and assistant messages and return deterministic chronological history. Conversation deletion cascades to messages. The message service validates and JSON-round-trips assistant Evidence Snapshots, rejects them on user messages, and leaves omitted snapshots `NULL`. Completed sync and SSE evidence paths persist version-1 canonical snapshots, including Combined partial outcomes and complete document sources. Reloaded assistant messages retain their message-owned snapshots for historical rendering. | No individual message mutation or pagination. |
| Synchronous assistant response | Implemented | Persist the user message, use one authoritative route, execute one selected evidence tool or the bounded combined manufacturing-plus-document workflow, validate evidence and the final answer, and persist one non-empty assistant response with its canonical snapshot when an evidence path produces one. | No system prompt, answer retry, model discovery, or planner. |
| Streaming assistant response | Implemented | Send SSE events for the persisted user message, bounded routing progress, token deltas, completion, safe errors, single-tool stages, and ordered path-aware combined stages. Completed evidence paths persist the same canonical snapshot contract as synchronous responses; current SSE tool events remain available. On completion, the frontend applies the returned persisted assistant message and clears current evidence. | Evidence-route answer text is buffered for deterministic post-checks before token events are forwarded. |
| Conversation continuity | Implemented | Previous user and assistant messages from the selected conversation are included in the next model request. | Workspace context is stored separately and is not yet included in the model prompt. |
| Workspace context API | Implemented | Read and partially update conversation-bound environment, device, lot, time range, and data source; synchronous and SSE production paths resolve saved device, lot, and supported synthetic time presets when tool arguments are missing. | Context is not injected into the general model prompt. Custom or unrecognized time-range labels still require clarification. |
| Synthetic device catalog | Implemented | `GET /devices` returns three deterministic fictional device identities and validates selected device IDs. | No live status, telemetry, production records, or mutable catalog. |
| React conversation workflow | Implemented | Load, create, select, and delete conversations; reload history; send messages through SSE; display routing, retry or fallback, tool, evidence, and response states; stop generation; and report failures. | There is no persisted trace timeline, message editing, regeneration, new-response counter, or pagination. |
| Industrial workspace shell | Implemented | Ant Design 6.5.1 and Ant Design X 2.9.0 provide a dark-first responsive workbench with grouped conversations, Bubble messages, a controlled Sender, XMarkdown, processing states, stable latest-message following, and current-exchange single or combined evidence. Combined exchanges keep manufacturing and document loading, empty, failure, and result regions separate. Reloaded assistant messages render canonical historical snapshots with a label and message capture time through the existing evidence panels; unavailable snapshots keep the message visible. | There is no persisted complete tool timeline, manufacturing chart surface, PDF ingestion, or multi-user document administration. |
| Context editor | Implemented | Select a fictional device, enter an optional lot, choose an executable 1, 4, 8, or 24 hour preset, keep edits in a local draft, Save or Reset explicitly, and guard navigation while changes are unsaved. Loading and failures remain visible in the inspector. | Data source and environment remain read-only synthetic metadata; arbitrary UTC start and end entry is not implemented. |
| Manufacturing domain | Implemented | Immutable Equipment, Production Lot, Inspection Record, Defect Count, Alarm Event, Time Range, Production Summary, Defect Distribution, and Equipment State Interval types; deterministic yield and ranked defect aggregation; overlapping alarm selection; explicit empty-result behavior; point-in-time recorded-status lookup; and one fictional AOI dataset. | Throughput is deferred until a later dataset and unit contract exists. There is no database persistence, live data, inferred equipment state, or causal analysis. |
| Production summary tool | Implemented | Typed `get_production_summary` request/result boundary filters the synthetic AOI dataset, delegates numeric work to the manufacturing domain, participates in synchronous and SSE grounded-answer flows, resolves missing arguments from supported workspace context, and returns current-exchange evidence. Its canonical snapshot is also rendered in historical assistant messages through the existing production panel. | Custom or unrecognized time-range labels require clarification. |
| Equipment status tool | Implemented | Typed `get_equipment_status` input and result contracts query explicit synthetic state intervals at one UTC timestamp, resolve missing time from supported workspace context, return `unknown` when no state is recorded, participate in synchronous and SSE flows, and persist canonical snapshots without treating recorded `unknown` as unavailable. | It is not live status. No status history or causal interpretation is provided. |
| Defect distribution tool | Implemented | Typed `get_defect_distribution` request and result contracts filter the synthetic AOI dataset, rank recorded defect categories by count, calculate shares against classified defects, expose unclassified failures and limitations, participate in synchronous and SSE flows, and persist canonical snapshots including valid empty results. | It does not infer causes, trends, or throughput. |
| LangGraph orchestration | Implemented | The synchronous graph and SSE runner share an application-owned route decision, deterministic clarification and fallback, single-tool execution, and one bounded manufacturing-then-document combined path. Combined validation checks manufacturing claims, any source IDs included in prose, causal conclusions, and unsupported operational claims while retaining valid evidence after model failure. | Structured Sources own traceability, so inline source IDs are optional. Validation is intentionally bounded to recognized claim forms; there are no persisted runs, planner, multiple manufacturing tools per turn, evidence-tool retries, checkpoints, resume behavior, or graph visualization. |
| Structured routing | Implemented | Immutable route contracts, a 38-scenario English and Traditional Chinese routing fixture, a high-confidence deterministic gate, one typed classifier call, a 1–30 second timeout, one retry, conservative fallback, safe logs, and shared sync/SSE decisions. | Explicit combined requests select exactly one manufacturing kind plus documents. Routing traces are not persisted, and broader multilingual support is not claimed. |
| Guided routing choices | Implemented | Combined-route clarifications persist two fixed application-owned actions. The latest unresolved actions survive reload, render as keyboard-accessible buttons, disable during submission, and send a normal user message through the existing SSE workflow. | Choices select one evidence path; they do not execute a multi-tool turn, accept model-generated actions, or use a special action endpoint. |
| RAG and sources | Implemented | An immutable corpus combines three protected fictional Markdown documents with persistent local uploads. Paragraph- and list-aware chunks stay within H2/H3 sections and use stable section-local citations. A fixed lexical gate, deterministic 256-dimensional feature-hashing embedding, and in-memory cosine index back `search_documents`, including bounded v0.9 query enrichment from recorded manufacturing fields. | Feature hashing is lexical rather than a semantic model. There is no PDF/OCR, external embedding service, persistent vector store, reranking, authentication, cloud storage, or causal inference. |
| MCP | Implemented | An independent official-SDK stdio server exposes `get_production_summary`, `get_equipment_status`, and `get_defect_distribution`. Discovery schemas reuse the native Pydantic contracts; calls return matching structured results plus deterministic text, reject unsupported fields, preserve safe domain errors, sanitize unexpected failures, and have an official-client lifecycle test. | Local stdio only. There is no HTTP transport, authentication, remote deployment, FastAPI, LangGraph, frontend, workspace-context, document-search, or live-data integration. |
| Evaluation and observability | Implemented | `industrial-agent-eval` runs a strict 45-scenario English and Traditional Chinese suite through existing routing, native tool, combined execution, retrieval, evidence, and answer-validation seams. It reports ten separate dimensions, records retries, fallback and monotonic stage timing, and writes an ignored typed JSON artifact with an exact fixture digest. | This is a deterministic offline baseline, not a model-quality benchmark. There is no LLM judge, live provider call, HTTP or frontend surface, persisted application trace, composite score, latency gate, or automatic baseline update. |

## v2.0 — Persistent Evidence and Model Working Notes

**Status: In Progress**

Slices 1 through 6 are implemented.
Slice 1 validates a version-1 typed
`MessageRead.evidence_snapshot` union for Production Summary, Equipment Status,
Defect Distribution, Document Search, Combined Evidence, and the explicit
Unavailable Evidence state. Slice 2 adds Alembic revision
`0006_add_evidence_snapshot` with nullable JSON `messages.evidence_snapshot`,
synchronizes the Message ORM model, keeps existing messages readable with
`NULL` after upgrade, and passes downgrade compatibility tests. Slice 3 adds a
narrow conversion and message-service write boundary:
`current_evidence_to_snapshot` converts the four typed single evidence outcomes
and Combined Evidence outcomes, including partial path results, into version-1
canonical snapshot JSON. The message service validates explicitly supplied
assistant Evidence Snapshot values, preserves their JSON round-trip, rejects
snapshots on user messages, and leaves omitted assistant snapshots as `NULL`.

Slice 3 persists canonical snapshots through the same assistant-message commit
path for all four single-evidence kinds and Combined success, failure, empty,
and bounded-fallback outcomes. Document Search retains complete source
snapshots, and synchronous and SSE completion return matching persisted data.
Snapshot construction failure, assistant insert failure, cancellation, and a
real-socket client disconnect leave the committed user message without an
assistant row or snapshot; database failure also rolls back the session. The
Slice 3 runtime suite reports 99 passed, with Ruff and `git diff --check`
passing.

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
Final v2.0 acceptance remains open in Slice 7.

## HTTP contracts

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/health` | Return API-process status. |
| `POST` | `/conversations` | Create a conversation with an optional title. |
| `GET` | `/conversations` | List conversations newest first. |
| `GET` | `/conversations/{conversation_id}` | Read one conversation. |
| `DELETE` | `/conversations/{conversation_id}` | Permanently delete a conversation and its messages. |
| `GET` | `/conversations/{conversation_id}/messages` | Return message history oldest first. |
| `POST` | `/conversations/{conversation_id}/messages` | Create a synchronous user/assistant exchange. |
| `POST` | `/conversations/{conversation_id}/messages/stream` | Create an SSE message exchange. |
| `GET` | `/conversations/{conversation_id}/context` | Read conversation-bound workspace context. |
| `PATCH` | `/conversations/{conversation_id}/context` | Partially update workspace context. |
| `GET` | `/devices` | List deterministic fictional device identities. |
| `GET` | `/documents` | List built-in and local Markdown documents; retain built-in metadata if local upload state is unavailable. |
| `POST` | `/documents` | Validate and add one UTF-8 Markdown file up to 1 MiB. |
| `GET` | `/documents/{document_id}` | Read one current built-in or local document by public ID. |
| `DELETE` | `/documents/{document_id}` | Delete one local upload after candidate corpus validation; protect built-ins. |

## Verification record

The latest full-release verification on 2026-08-15 produced:

- API: 416 Pytest tests and Ruff passed. No backend static type checker is
  configured in the current development dependency set.
- Evaluation: all 45 formal scenarios passed. The observed dimension totals
  were route 33/33, tool selection 16/16, argument resolution 4/4, evidence
  parity 13/13, retrieval top-one 9/9, retrieval top-three 12/12, citation 4/4,
  safe failure 9/9, unsupported-claim rejection 5/5, and retry or fallback
  2/2. Elapsed values are local observations, not performance guarantees.
- MCP observation: one local official-client run initialized the stdio server
  in 380.98 ms and completed `get_production_summary` in 16.29 ms. These are
  development-machine observations; the matching direct native call took 0.40
  ms. This single comparison is not a performance guarantee or benchmark.
- Slice 4 was verified separately on 2026-08-17: 69 focused frontend tests and
  41 backend contract tests passed. The full Web suite then passed 127 Vitest
  tests and TypeScript checking; ESLint completed with the existing Fast
  Refresh warning, and the Vite production build completed.
- Slice 5 was verified separately on 2026-08-17: 51 focused provider-reasoning
  tests passed, and the full API suite then passed 459 tests. Ruff and
  `git diff --check` passed.
- Slice 6 was verified separately on 2026-08-17: 89 focused backend tests and
  86 focused frontend tests passed. The full API suite then passed 463 tests
  and the full Web suite passed 144 tests; type checking, linting, builds,
  Ruff, and `git diff --check` passed. The existing Ant Design CLI
  native-binding block remains. Reproducible browser acceptance passed with an
  independent OpenAI-compatible streaming fixture: the disclosure opened
  during reasoning, closed on the first Final Answer token, reopened by
  pointer interaction, and cleared on reload while the answer remained. At
  390px there was no horizontal page overflow; the reasoning body was bounded
  at 220px with overflow scrolling, and the disclosure showed a visible focus
  outline. This does not claim a live Qwen reasoning pass; its routing delay
  was excluded from deterministic UI acceptance. The browser run upgraded the
  local Alembic database from `0005` to `0006` without deleting data.
- Browser combined workflow: one explicit production-plus-document request ran
  against saved synthetic AOI context. The final exchange retained a 95.56%
  Production Summary and three cited document sources when model synthesis was
  unavailable. At 390 px, the page and document root both remained 390 px wide
  with no horizontal overflow.
- Browser: the connected local stack listed three built-ins, uploaded one
  valid Markdown document, rejected its duplicate, deleted the local upload,
  restored focus to the Documents trigger, and showed no page-level horizontal
  overflow at 390 px. The configured model did not choose `search_documents`
  for the uploaded test term, so the local-source card remains covered by API,
  workflow, and frontend contract tests rather than that browser run.
- Browser routing: a fresh conversation produced deterministic clarification
  for missing evidence context, rejected a request for private live records,
  and handled a Traditional Chinese equipment-status request against saved
  synthetic context with an explicit no-recorded-status response.
- Browser guided choices: a combined request exposed the two fixed actions,
  retained them after reload, sent one normal production-evidence message from
  the selected action, removed the resolved choices, and completed with the
  deterministic Production summary surface. The configured model took about
  23 seconds to finish the answer after evidence arrived.
- Ant Design CLI `info`, `lint`, `doctor`, and `bug-cli` were blocked at startup
  because the global CLI installation is missing the
  `@oxc-parser/binding-darwin-arm64` optional native package. No Ant Design
  component API changed in this slice; TypeScript, ESLint, tests, and the
  production build still passed. No browser acceptance was run for Slice 4.
- Clean copy: git archive output installed API and Web dependencies from the
  committed lockfiles, applied all migrations, and reran the API and Web test
  suites successfully.

The existing Vite build reports a JavaScript chunk-size warning above 500 kB;
the warning is retained. The 2026-08-17 Slice 4 build reported a 958.86 kB main
JavaScript output, or 309.44 kB gzip, while XMarkdown remained a 125.66 kB lazy
chunk, or 41.52 kB gzip. The initial JavaScript gzip size remains above the
earlier 244.02 kB baseline. XMarkdown is already lazy, and no loading boundary
or warning threshold changed in Slice 4.

## Remaining hardening

The v0.1 clean-environment acceptance item is complete. A real-socket
integration test now verifies that a streaming client disconnect before
completion leaves the persisted user message without creating a partial
assistant message. Provider-side generation cancellation is not guaranteed.

v1.0 is Implemented. Its release boundary passed local deterministic checks,
accepted product screenshots, final public-copy and publication review,
two-axis code review, and GitHub Actions on 2026-08-15.
The v1.0 browser run also exposed and verified a first-stream rendering race:
the workspace now defers Ant Design X list scrolling until the mounted frame
instead of calling its imperative handle during the mounting layout effect.
The same run rejected two screenshot candidates: `llama3.1:8b` reached the
combined safe fallback after evidence retrieval, while `deepseek-r1:7b` left
the manufacturing path unavailable. These are valid degraded or partial-
failure observations, not the required Combined Evidence happy path.
`qwen3:14b` later passed a direct OpenAI-compatible tool-call smoke test. After
the demo lot was corrected to the repository-owned `LOT-DEMO-001`, the full
browser workflow produced both deterministic manufacturing evidence and three
document sources, but its final synthesis still failed grounding validation.
The validator now keeps deterministic manufacturing and claim boundaries
strict without requiring inline citations or rejecting formatting-only
numbers. A later `qwen3:14b` browser run passed this revised boundary and was
captured at the default desktop viewport and 390 px. The 390 px review also
found and corrected a narrow-screen Production Summary layout regression. The
final accepted run required every possible interpretation to state that
validation was still required.

## Truthfulness notes

The interface includes industrial prompt suggestions, synthetic context, and
a focused SSE path for production questions. Supported workspace
presets can now complete missing production-query arguments. Yield, defect, and
alarm answers are grounded only when the configured model returns a supported
production-summary or defect-distribution tool call with resolvable arguments.
Other model output must
not be presented as verified domain evidence. Equipment status evidence comes
from recorded synthetic intervals, not live machinery. Causal analysis is not
implemented.
