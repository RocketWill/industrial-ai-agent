# Implementation Status

This document is the code-backed feature inventory for the repository. It was
reviewed against the application code, migrations, tests, and public
documentation on 2026-08-01.

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
| Database foundation | Implemented | SQLite, synchronous SQLAlchemy sessions, foreign-key enforcement, and four explicit Alembic revisions. | Application startup does not create or migrate schema. |
| Conversations | Implemented | Create, list newest first, open, and permanently delete conversations. | No rename, archive, restore, or pagination. |
| Message history | Implemented | Persist user and assistant messages and return deterministic chronological history. Conversation deletion cascades to messages. | No individual message mutation or pagination. |
| Synchronous assistant response | Implemented | Persist the user message, send complete conversation history to an OpenAI-compatible model, optionally execute one supported production-summary tool call, and persist one successful final assistant response. | No system prompt, retry policy, model discovery, or structured evidence in the HTTP response. |
| Streaming assistant response | Implemented | Send SSE events for the persisted user message, token deltas, completion, and safe errors. Persist the assistant response only after the backend consumes a non-empty completed stream. | The browser can abort its request, but disconnect persistence behavior does not yet have an integration test. |
| Conversation continuity | Implemented | Previous user and assistant messages from the selected conversation are included in the next model request. | Workspace context is stored separately and is not yet included in the model prompt. |
| Workspace context API | Implemented | Read and partially update conversation-bound environment, device, lot, time range, and data source; the synchronous production path resolves saved device, lot, and supported synthetic time presets when tool arguments are missing. | Context is not injected into the general model prompt. Custom or unrecognized time-range labels still require clarification. |
| Synthetic device catalog | Implemented | `GET /devices` returns three deterministic fictional device identities and validates selected device IDs. | No live status, telemetry, production records, or mutable catalog. |
| React conversation workflow | Implemented | Load, create, select, and delete conversations; reload history; send messages; display incremental responses; stop generation; route a focused English production-query keyword set to the synchronous endpoint; and report failures. | No structured intent contract, message editing, regeneration, new-response counter, or pagination. |
| Industrial workspace shell | Implemented | Dithered Ant Design theme, desktop sidebar, mobile Drawer, analysis workspace header, explicit synthetic context strip, fixed composer, one main message scrollbar, responsive reading widths, scroll-to-bottom control, and a compact production evidence summary card. | Tool timelines, sources, and manufacturing charts are not displayed; evidence is available only for the current synchronous exchange. |
| Context editor | Implemented | Select a fictional device, enter an optional lot, choose a time-range preset, and save conversation context. | Source remains read-only Synthetic Demo; `Custom` does not provide start/end controls. |
| Manufacturing domain | In Progress | Immutable Equipment, Production Lot, Inspection Record, Defect Count, Alarm Event, Time Range, and Production Summary types; deterministic yield and defect aggregation; overlapping alarm selection; explicit empty-result behavior; and one fictional AOI dataset. | No database persistence, equipment-status semantics, throughput calculation, live data, or causal inference. |
| Production summary tool | In Progress | Typed `get_production_summary` request/result boundary filters the synthetic AOI dataset, delegates numeric work to the manufacturing domain, participates in the synchronous grounded-answer flow, resolves missing arguments from supported workspace context, and returns optional evidence through the synchronous message contract. | Evidence is not persisted or available through SSE/history; custom or unrecognized time-range labels require clarification. |
| LangGraph orchestration | Implemented | The synchronous path invokes a compiled typed graph with context loading, focused production-query detection, one supported tool execution, evidence handoff, final model completion, and persistence. The SSE runner reuses state and persistence boundaries while emitting token events directly. | No persisted runs, general intent router, SSE tool execution, retries, checkpoints, resume behavior, or graph visualization. Tool execution currently occurs within the model-call step rather than a separate graph node. |
| RAG and sources | Planned | None. | No document ingestion, vector storage, retrieval, citation, or source viewer. |
| MCP | Planned | None. | No MCP server or client integration. |
| Evaluation and observability | Planned | None. | No scenario suite, tool trace, latency panel, or retry telemetry. |

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

## Verification record

The latest full local verification on 2026-08-01 produced:

- API: 148 Pytest tests passed and Ruff passed. Package build was not rerun in
  the current environment because its virtual environment does not include the
  `build` module; the prior clean-copy source and wheel build remains recorded.
- Web: 35 Vitest tests passed, TypeScript checking passed, ESLint passed, and
  the Vite production build completed.
- Browser: desktop and mobile shell checks confirmed viewport-bound layout,
  hidden body overflow, mobile navigation switching, and the conversation list
  as the primary vertical scroll region.
- Clean copy: git archive output installed API and Web dependencies from the
  committed lockfiles, applied all migrations, and reran the API and Web test
  suites successfully.

The Vite build reports a JavaScript chunk-size warning above 500 kB. This is a
build warning rather than a failed verification, and code splitting has not
yet been introduced.

## Remaining hardening

The v0.1 clean-environment acceptance item is complete. Client-disconnect
persistence behavior for streaming still needs a dedicated integration test;
this does not block the current v0.1 or v0.1.1 status.

## Truthfulness notes

The interface includes industrial prompt suggestions, synthetic context, and
a focused synchronous path for production questions. Supported workspace
presets can now complete missing production-query arguments. Yield, defect, and
alarm answers are grounded only when the configured model returns the supported
production-summary tool call with complete arguments. Other model output must
not be presented as verified domain evidence. Equipment status and causal
analysis are not implemented.
