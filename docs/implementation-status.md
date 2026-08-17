# Implementation Status

This document is the code-backed feature inventory for the repository. It was
reviewed against the application code, migrations, tests, and public
documentation on 2026-08-15. The latest recorded verification run remains
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
| Message history | Implemented | Persist user and assistant messages and return deterministic chronological history. Conversation deletion cascades to messages. The message service validates and JSON-round-trips assistant Evidence Snapshots, rejects them on user messages, and leaves omitted snapshots `NULL`. Completed sync and SSE evidence paths persist version-1 canonical snapshots, including Combined partial outcomes and complete document sources. | No individual message mutation or pagination. Historical API convergence, reload rendering, and UI consumption remain open in Slice 4. |
| Synchronous assistant response | Implemented | Persist the user message, use one authoritative route, execute one selected evidence tool or the bounded combined manufacturing-plus-document workflow, validate evidence and the final answer, and persist one non-empty assistant response. | No system prompt, answer retry, model discovery, planner, or historical evidence reload. |
| Streaming assistant response | Implemented | Send SSE events for the persisted user message, bounded routing progress, token deltas, completion, safe errors, single-tool stages, and ordered path-aware combined stages. Completed evidence paths persist the same canonical snapshot contract as synchronous responses. | Evidence-route answer text is buffered for deterministic post-checks before token events are forwarded. Historical reload rendering remains open in Slice 4. |
| Conversation continuity | Implemented | Previous user and assistant messages from the selected conversation are included in the next model request. | Workspace context is stored separately and is not yet included in the model prompt. |
| Workspace context API | Implemented | Read and partially update conversation-bound environment, device, lot, time range, and data source; synchronous and SSE production paths resolve saved device, lot, and supported synthetic time presets when tool arguments are missing. | Context is not injected into the general model prompt. Custom or unrecognized time-range labels still require clarification. |
| Synthetic device catalog | Implemented | `GET /devices` returns three deterministic fictional device identities and validates selected device IDs. | No live status, telemetry, production records, or mutable catalog. |
| React conversation workflow | Implemented | Load, create, select, and delete conversations; reload history; send messages through SSE; display routing, retry or fallback, tool, evidence, and response states; stop generation; and report failures. | There is no persisted trace timeline, message editing, regeneration, new-response counter, or pagination. |
| Industrial workspace shell | Implemented | Ant Design 6.5.1 and Ant Design X 2.9.0 provide a dark-first responsive workbench with grouped conversations, Bubble messages, a controlled Sender, XMarkdown, processing states, stable latest-message following, and current-exchange single or combined evidence. Combined exchanges keep manufacturing and document loading, empty, failure, and result regions separate. | There is no persisted evidence history, complete tool timeline, manufacturing chart surface, PDF ingestion, or multi-user document administration. |
| Context editor | Implemented | Select a fictional device, enter an optional lot, choose an executable 1, 4, 8, or 24 hour preset, keep edits in a local draft, Save or Reset explicitly, and guard navigation while changes are unsaved. Loading and failures remain visible in the inspector. | Data source and environment remain read-only synthetic metadata; arbitrary UTC start and end entry is not implemented. |
| Manufacturing domain | Implemented | Immutable Equipment, Production Lot, Inspection Record, Defect Count, Alarm Event, Time Range, Production Summary, Defect Distribution, and Equipment State Interval types; deterministic yield and ranked defect aggregation; overlapping alarm selection; explicit empty-result behavior; point-in-time recorded-status lookup; and one fictional AOI dataset. | Throughput is deferred until a later dataset and unit contract exists. There is no database persistence, live data, inferred equipment state, or causal analysis. |
| Production summary tool | Implemented | Typed `get_production_summary` request/result boundary filters the synthetic AOI dataset, delegates numeric work to the manufacturing domain, participates in synchronous and SSE grounded-answer flows, resolves missing arguments from supported workspace context, and returns current-exchange evidence. | Focused sync/SSE runtime tests verify canonical snapshot attachment; historical reload and UI consumption remain incomplete. Custom or unrecognized time-range labels require clarification. |
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

Slices 1 through 3 are implemented.
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

Historical API convergence and reload rendering remain open in Slice 4.
Provider reasoning parsing, Model Working Notes, and final v2.0 acceptance
remain open in Slices 5 through 7.

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

The latest local verification on 2026-08-15 produced:

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
- Web: 106 Vitest tests passed, TypeScript checking passed, ESLint passed, and
  the Vite production build completed.
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
- Ant Design CLI diagnostics could not start because the global CLI installation
  is missing the `@oxc-parser/binding-darwin-arm64` optional native package.
  The CLI's own `bug-cli` preview fails at the same startup boundary. No Ant
  Design component API changed in this slice; TypeScript, ESLint, tests, and
  the production build still passed.
- Clean copy: git archive output installed API and Web dependencies from the
  committed lockfiles, applied all migrations, and reran the API and Web test
  suites successfully.

The Vite build reports a JavaScript chunk-size warning above 500 kB. The main
JavaScript output is 956.41 kB, or 310.35 kB gzip as reported under Node.js 24,
while XMarkdown is split into
a 125.66 kB lazy chunk, or 41.52 kB gzip. The initial JavaScript gzip size is
above the earlier 244.02 kB baseline. A direct `gzip -9` measurement of the
unchanged main artifact was 308.47 kB; the difference from the previous Vite
report is compressor/runtime behavior rather than source growth. XMarkdown is
already lazy, and further splitting would change component or loading
boundaries, so no release-only chunk rewrite or warning-threshold increase was
made.

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
