# Implementation Status

This document is the code-backed feature inventory for the repository. It was
reviewed against the application code, migrations, tests, and public
documentation on 2026-08-10.

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
| Database foundation | Implemented | SQLite, synchronous SQLAlchemy sessions, foreign-key enforcement, and five explicit Alembic revisions. | Application startup does not create or migrate schema. |
| Conversations | Implemented | Create, list newest first, open, and permanently delete conversations. | No rename, archive, restore, or pagination. |
| Message history | Implemented | Persist user and assistant messages and return deterministic chronological history. Conversation deletion cascades to messages. | No individual message mutation or pagination. |
| Synchronous assistant response | Implemented | Persist the user message, use one authoritative route, optionally execute one selected production-summary, equipment-status, defect-distribution, or document-search tool, validate evidence and the final answer, and persist one successful assistant response. | No system prompt, answer retry, model discovery, multi-tool turn, or persisted evidence history. |
| Streaming assistant response | Implemented | Send SSE events for the persisted user message, bounded routing progress, token deltas, completion, safe errors, and supported tool stages (`tool_call_started`, `tool_result`). The same route and evidence policy is used by the synchronous path. | Evidence-route output is buffered for deterministic post-checks before token events are forwarded. Client disconnect persistence behavior does not yet have an integration test. |
| Conversation continuity | Implemented | Previous user and assistant messages from the selected conversation are included in the next model request. | Workspace context is stored separately and is not yet included in the model prompt. |
| Workspace context API | Implemented | Read and partially update conversation-bound environment, device, lot, time range, and data source; synchronous and SSE production paths resolve saved device, lot, and supported synthetic time presets when tool arguments are missing. | Context is not injected into the general model prompt. Custom or unrecognized time-range labels still require clarification. |
| Synthetic device catalog | Implemented | `GET /devices` returns three deterministic fictional device identities and validates selected device IDs. | No live status, telemetry, production records, or mutable catalog. |
| React conversation workflow | Implemented | Load, create, select, and delete conversations; reload history; send messages through SSE; display routing, retry or fallback, tool, evidence, and response states; stop generation; and report failures. | There is no persisted trace timeline, message editing, regeneration, new-response counter, or pagination. |
| Industrial workspace shell | Implemented | Ant Design 6.5.1 and Ant Design X 2.9.0 provide a dark-first responsive workbench with grouped conversations, Bubble messages, a controlled Sender, XMarkdown, processing states, stable latest-message following, and current-exchange production or document evidence. Retrieved sources can open a read-only full-document Drawer positioned at the cited section. A separate Documents drawer manages the active Markdown corpus. | There is no persisted evidence history, complete tool timeline, manufacturing chart surface, PDF ingestion, or multi-user document administration. |
| Context editor | Implemented | Select a fictional device, enter an optional lot, choose an executable 1, 4, 8, or 24 hour preset, keep edits in a local draft, Save or Reset explicitly, and guard navigation while changes are unsaved. Loading and failures remain visible in the inspector. | Data source and environment remain read-only synthetic metadata; arbitrary UTC start and end entry is not implemented. |
| Manufacturing domain | Implemented | Immutable Equipment, Production Lot, Inspection Record, Defect Count, Alarm Event, Time Range, Production Summary, Defect Distribution, and Equipment State Interval types; deterministic yield and ranked defect aggregation; overlapping alarm selection; explicit empty-result behavior; point-in-time recorded-status lookup; and one fictional AOI dataset. | Throughput is deferred until a later dataset and unit contract exists. There is no database persistence, live data, inferred equipment state, or causal analysis. |
| Production summary tool | Implemented | Typed `get_production_summary` request/result boundary filters the synthetic AOI dataset, delegates numeric work to the manufacturing domain, participates in synchronous and SSE grounded-answer flows, resolves missing arguments from supported workspace context, and returns current-exchange evidence. | Evidence is not persisted in history; custom or unrecognized time-range labels require clarification. |
| Equipment status tool | Implemented | Typed `get_equipment_status` input and result contracts query explicit synthetic state intervals at one UTC timestamp, resolve missing time from supported workspace context, return `unknown` when no state is recorded, participate in synchronous and SSE flows, and render current-exchange evidence. | It is not live status. Evidence is not persisted, and no status history or causal interpretation is provided. |
| Defect distribution tool | Implemented | Typed `get_defect_distribution` request and result contracts filter the synthetic AOI dataset, rank recorded defect categories by count, calculate shares against classified defects, expose unclassified failures and limitations, participate in synchronous and SSE flows, and render current-exchange evidence. | It does not infer causes, trends, or throughput. Evidence is not persisted. |
| LangGraph orchestration | Implemented | The synchronous graph and SSE runner share an application-owned route decision, deterministic clarification and fallback, one selected tool execution, evidence validation, final-answer checks, and persistence boundaries. Valid evidence remains visible when a generated answer fails citation or numeric verification, with a route-specific explanation replacing the rejected answer. | No persisted runs, multi-tool turns, evidence-tool retries, checkpoints, resume behavior, or graph visualization. Tool execution remains inside the model-call step rather than a separate graph node. |
| Structured routing | Implemented | Immutable route contracts, a 38-scenario English and Traditional Chinese fixture, a high-confidence deterministic gate, one typed classifier call, a 1–30 second timeout, one retry, conservative fallback, safe logs, and shared sync/SSE decisions. | Combined requests ask the user to select one path. Routing traces are not persisted, and broader multilingual support is not claimed. |
| Guided routing choices | Implemented | Combined-route clarifications persist two fixed application-owned actions. The latest unresolved actions survive reload, render as keyboard-accessible buttons, disable during submission, and send a normal user message through the existing SSE workflow. | Choices select one evidence path; they do not execute a multi-tool turn, accept model-generated actions, or use a special action endpoint. |
| RAG and sources | Implemented | An immutable corpus combines three protected fictional Markdown documents with persistent local uploads. Paragraph- and list-aware chunks stay within H2/H3 sections and use stable section-local citations. A fixed lexical gate, deterministic 256-dimensional feature-hashing embedding, and in-memory cosine index back `search_documents`. The API and Drawers support source reading, single-file upload, validation, atomic corpus replacement, provenance, and local deletion. | Feature hashing is lexical rather than a semantic model. There is no PDF/OCR, external embedding service, persistent vector store, reranking, authentication, cloud storage, or combined production-and-document turn. |
| MCP | Implemented | An independent official-SDK stdio server exposes `get_production_summary`, `get_equipment_status`, and `get_defect_distribution`. Discovery schemas reuse the native Pydantic contracts; calls return matching structured results plus deterministic text, reject unsupported fields, preserve safe domain errors, sanitize unexpected failures, and have an official-client lifecycle test. | Local stdio only. There is no HTTP transport, authentication, remote deployment, FastAPI, LangGraph, frontend, workspace-context, document-search, or live-data integration. |
| Evaluation and observability | Implemented | `industrial-agent-eval` runs a strict 30-scenario English and Traditional Chinese suite through existing routing, native tool, retrieval, evidence, and answer-validation seams. It reports ten separate dimensions, preserves the approved retrieval thresholds, records retries, fallback and monotonic stage timing, and writes an ignored typed JSON artifact with an exact fixture digest. | This is a deterministic offline baseline, not a model-quality benchmark. There is no LLM judge, live provider call, HTTP or frontend surface, persisted application trace, composite score, latency gate, or automatic baseline update. |

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

The latest local verification on 2026-08-10 produced:

- API: 385 Pytest tests passed, Ruff passed, the uv lockfile passed its
  consistency check, and source and wheel builds completed.
- Evaluation: all 30 formal scenarios passed. The observed dimension totals
  were route 18/18, tool selection 4/4, argument resolution 4/4, evidence
  parity 5/5, retrieval top-one 9/9, retrieval top-three 12/12, citation 2/2,
  safe failure 6/6, unsupported-claim rejection 2/2, and retry or fallback
  2/2. Elapsed values are local observations, not performance guarantees.
- MCP observation: one local official-client run initialized the stdio server
  in 380.98 ms and completed `get_production_summary` in 16.29 ms. These are
  development-machine observations; the matching direct native call took 0.40
  ms. This single comparison is not a performance guarantee or benchmark.
- Web: 98 Vitest tests passed, TypeScript checking passed, ESLint passed, and
  the Vite production build completed.
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
JavaScript output is 951.48 kB, or 307.93 kB gzip, while XMarkdown is split into
a 125.66 kB lazy chunk, or 41.52 kB gzip. The initial JavaScript gzip size is
above the recorded 244.02 kB baseline. This remains at the review threshold;
the next frontend dependency change should revisit initial chunk composition
before expanding the UI further.

## Remaining hardening

The v0.1 clean-environment acceptance item is complete. Client-disconnect
persistence behavior for streaming still needs a dedicated integration test;
this does not block the current v0.1 or v0.1.1 status.

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
