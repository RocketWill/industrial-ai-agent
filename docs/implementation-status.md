# Implementation Status

This document is the code-backed feature inventory for the repository. It was
reviewed against the application code, migrations, tests, and public
documentation on 2026-07-31.

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
| Synchronous assistant response | Implemented | Persist the user message, send complete conversation history to an OpenAI-compatible model, and persist one successful assistant response. | No system prompt, tool calling, retry policy, or model discovery. |
| Streaming assistant response | Implemented | Send SSE events for the persisted user message, token deltas, completion, and safe errors. Persist the assistant response only after the backend consumes a non-empty completed stream. | The browser can abort its request, but disconnect persistence behavior does not yet have an integration test. |
| Conversation continuity | Implemented | Previous user and assistant messages from the selected conversation are included in the next model request. | Workspace context is stored separately and is not yet included in the model prompt. |
| Workspace context API | Implemented | Read and partially update conversation-bound environment, device, lot, time range, and data source. | Context is metadata only; it does not trigger data queries or model grounding. |
| Synthetic device catalog | Implemented | `GET /devices` returns three deterministic fictional device identities and validates selected device IDs. | No live status, telemetry, production records, or mutable catalog. |
| React conversation workflow | Implemented | Load, create, select, and delete conversations; reload history; send messages; display incremental responses; stop generation; and report failures. | No message editing, regeneration, new-response counter, or pagination. |
| Industrial workspace shell | Implemented | Dithered Ant Design theme, desktop sidebar, mobile Drawer, fixed workspace header and composer, one main message scrollbar, responsive reading widths, and scroll-to-bottom control. | Production Data, Knowledge Base, and Evaluations remain visibly marked as planned. |
| Context editor | Implemented | Select a fictional device, enter an optional lot, choose a time-range preset, and save conversation context. | Source remains read-only Synthetic Demo; `Custom` does not provide start/end controls. |
| Manufacturing analytics | Planned | None. | No yield, throughput, defect, alarm, or equipment-status calculation. |
| LangGraph orchestration | Planned | None. | The Message API calls the adapter directly. |
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

The latest full local verification on 2026-07-31 produced:

- API: 118 Pytest tests passed, Ruff passed, and the source and wheel builds
  completed.
- Web: 34 Vitest tests passed, TypeScript checking passed, ESLint passed, and
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

The interface includes industrial prompt suggestions and synthetic context to
show the intended workflow. They are not evidence of manufacturing analytics.
Until deterministic tools and synthetic datasets are implemented, model
answers about yield, alarms, defects, or equipment status are ungrounded model
output and must not be presented as verified production results.
