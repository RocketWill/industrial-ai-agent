# Web

## Purpose

This directory contains the React and TypeScript v0.1 conversation foundation.

## Implemented

- Vite, React, TypeScript, Ant Design, Vitest, and React Testing Library;
- a `GET /health` client with runtime response validation;
- conversation loading, creation, selection, and deletion through the existing API;
- persisted message history and synchronous user/assistant exchanges;
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

- add broader clean-environment documentation and verified limitations;
- continue testing the synchronous workflow against local API configuration.

The current conversation workflow uses the synchronous Message API. It keeps
draft text after failed submissions and introduces no streaming behavior.

## Non-responsibilities

Streaming, agent traces, tool timelines, RAG sources, manufacturing charts,
authentication, and administrative interfaces are outside v0.1.

## Current status

**In Progress** — the health, conversation-navigation, and synchronous message
foundations and Dithered dark UI foundation are implemented and verified.
Streaming remains planned.
