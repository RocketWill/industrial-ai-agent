# Web

## Purpose

This directory contains the React and TypeScript conversation and analysis
workbench implemented across the frontend milestones.

## Implemented

- Vite, React, TypeScript, Ant Design 6.5.1, Ant Design X 2.9.0, XMarkdown
  2.9.0, Vitest, and React Testing Library;
- a `GET /health` client with runtime response validation;
- conversation loading, creation, selection, and deletion through the existing API;
- persisted message history and synchronous user/assistant exchanges;
- synchronous production-question fallback for a focused English keyword set;
- deterministic Production Summary result surface for the current exchange,
  including Defect Counts, Alarm Events, provenance, and empty states;
- deterministic Equipment Status evidence for an explicit synthetic
  observation time, including its effective interval and limitations;
- deterministic Defect Distribution evidence with ranked categories, shares,
  classified counts, unclassified failures, and limitations;
- retrieved Sources evidence with fictional document title, section, excerpt,
  match score, stable source ID, and repository-relative path;
- SSE streaming assistant responses with a keyboard-accessible Stop action;
- conversation-bound context display and editing;
- deterministic fictional device selection, lot validation, and time-range
  presets;
- a dark-first three-column desktop workbench, two-column tablet layout, and
  focused navigation and context Drawers on mobile;
- grouped conversations and a draft-based context inspector with Save, Reset,
  validation, and unsaved-change protection;
- a viewport-bound message stream with Markdown assistant responses, pending
  tool stages, current-exchange evidence, stable latest-message following, and
  a jump-to-latest control;
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

The lockfile records the exact dependency graph. Use a currently supported
Node.js release rather than relying on the previously documented Node.js 16
environment.

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
and uses the v0.1.1 streaming endpoint in the browser. Production questions
receive tool-stage and evidence events before the completed answer. General
questions retain provider token streaming. The browser keeps draft text after
failed submissions and does not persist partial assistant output.

## Non-responsibilities

Complete agent traces, tool timelines, PDF or batch ingestion, manufacturing
charts, authentication, and administrative interfaces remain outside the
implemented frontend scope. Streaming was added in v0.1.1; current production,
source evidence, and local Markdown management depend on the later v0.4 and
v0.5 contracts.

## Current status

The web behavior for v0.1, v0.1.1, and v0.1.2 is implemented and verified.
Streaming uses `fetch` and `ReadableStream`, renders token deltas in memory, and
offers a keyboard-accessible Stop action. The browser does not treat partial
assistant text as persisted; the backend creates the record only after it
consumes a complete non-empty stream. Client-disconnect persistence still
needs a dedicated integration test.

The analysis context inspector loads conversation-bound metadata from the API.
It allows a device to be selected from the fictional catalog and optional lot
and supported time-range values to be saved. Changes remain local until Save,
Reset restores the latest server state, and unsaved changes are guarded before
navigation. The source and environment metadata remain read-only.

Grounded production results appear as final assistant text with a compact
structured summary, recorded status, ranked defect distribution, or retrieved
fictional sources attached to the assistant bubble that produced it. Pending
assistant bubbles use an accessible three-dot processing indicator and an
Ant Design BorderBeam while a response is active. Completed bubbles retain a
static multicolor bottom accent. Generating and production-tool stages remain
distinguishable through text and ARIA state.

The workspace header also opens a Documents drawer. It lists protected
repository documents and local uploads, validates one `.md` file up to 1 MiB,
shows indexing and failure states, and confirms local deletion by document
name. The drawer warns that files remain on local disk and that retrieved text
may be sent to the configured model.

Evidence is not persisted across reloads, and the browser does not display a
full tool timeline or manufacturing charts. Its keyword heuristic does not yet
cover Chinese production terms or distinguish every conceptual question from
a data query.
