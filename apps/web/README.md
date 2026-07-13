# Web

## Purpose

This directory contains the React and TypeScript v0.1 conversation foundation.

## Implemented

- Vite, React, TypeScript, Ant Design, Vitest, and React Testing Library;
- a `GET /health` client with runtime response validation;
- conversation loading, creation, selection, and deletion through the existing API;
- persisted message history and synchronous user/assistant exchanges;
- SSE streaming assistant responses with a keyboard-accessible Stop action;
- conversation-bound context display and editing;
- deterministic fictional device selection, lot validation, and time-range
  presets;
- desktop sidebar navigation and a mobile Drawer;
- a viewport-bound shell with one primary conversation scrollbar;
- assistant reasoning-tag suppression, message copy, empty states, and a
  scroll-to-bottom control;
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

## Verification status

The documented workflow has been verified from a clean git archive copy using
the committed npm lockfile and frontend test, typecheck, lint, and build
commands.

The conversation workflow keeps the synchronous Message API as a stable path
and also supports the v0.1.1 streaming endpoint. It keeps draft text after
failed submissions and does not persist partial assistant output.

## Non-responsibilities

Agent traces, tool timelines, RAG sources, manufacturing charts, authentication,
and administrative interfaces are outside v0.1. Streaming is implemented in
the separate v0.1.1 milestone.

## Current status

The web behavior for v0.1, v0.1.1, and v0.1.2 is implemented and verified.
Streaming uses `fetch` and `ReadableStream`, renders token deltas in memory, and
offers a keyboard-accessible Stop action. The browser does not treat partial
assistant text as persisted; the backend creates the record only after it
consumes a complete non-empty stream. Client-disconnect persistence still
needs a dedicated integration test.

The context bar loads conversation-bound metadata from the API. Its Drawer
allows a device to be selected from the fictional catalog and optional lot and
time-range values to be saved. Empty values appear as `Not configured`, and the
source remains read-only `Synthetic Demo`.

The sidebar exposes only the implemented analysis workspace. The empty-state
prompts describe synthetic conversation tasks rather than implying that
production analytics are available. The current application has no
manufacturing tools or datasets to ground equipment, yield, alarm, or defect
answers.
