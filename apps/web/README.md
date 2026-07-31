# Web

## Purpose

This directory contains the React and TypeScript v0.1 conversation foundation.

## Implemented

- Vite, React, TypeScript, Ant Design, Vitest, and React Testing Library;
- a `GET /health` client with runtime response validation;
- conversation loading, creation, selection, and deletion through the existing API;
- persisted message history and synchronous user/assistant exchanges;
- SSE streaming assistant responses with a keyboard-accessible Stop action;
- local `/api` proxying to `http://127.0.0.1:8000` during Vite development;
- checking, connected, and unavailable API-process states; and
- a user-initiated `Check again` action that prevents duplicate in-flight
  health requests.

The health endpoint reports only whether the API process responds. It does not
confirm database, LLM, or future manufacturing-tool availability.

## Setup

From `apps/web`:

```bash
npm ci
```

The current project uses versions compatible with the local Node.js 16 runtime.
The lockfile records the exact dependency graph.

## Run

Start the API in a separate terminal from `apps/api` after applying migrations:

```bash
uv run alembic upgrade head
uv run uvicorn industrial_agent.main:app --host 127.0.0.1 --port 8000
```

Then start the browser application from `apps/web`:

```bash
npm run dev
```

The browser requests `/api/health`, which Vite proxies to the local API. Set
`VITE_API_BASE_URL` only when the browser needs a different public API base
URL. Do not put secrets, credentials, or private endpoints in Vite environment
variables.

## Verify

```bash
npm test
npm run typecheck
npm run lint
npm run build
```

## Remaining v0.1 responsibilities

- add broader clean-environment documentation and verified limitations.

The conversation workflow keeps the synchronous Message API as a stable path
and also supports the v0.1.1 streaming endpoint. It keeps draft text after
failed submissions and does not persist partial assistant output.

## Non-responsibilities

Agent traces, tool timelines, RAG sources, manufacturing charts, authentication,
and administrative interfaces are outside v0.1. Streaming is implemented in
the separate v0.1.1 milestone.

## Current status

**In Progress** — the health, conversation-navigation, and synchronous message
foundations and Dithered dark UI foundation are implemented and verified.
Streaming is available through the message composer. The client consumes SSE
frames with `fetch` and `ReadableStream`, renders token deltas in memory, and
offers a keyboard-accessible Stop action. Partial or cancelled assistant text
is not persisted.

The current shell presents these capabilities as a semiconductor Agent
workbench. Its navigation marks Production Data, Knowledge Base, and Evaluations
as planned, and it labels the current portfolio context as `Synthetic Demo
Data`.
