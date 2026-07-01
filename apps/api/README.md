# API

## Purpose

This application provides the HTTP backend for the Industrial AI Agent
portfolio project.

## Implemented

- FastAPI application factory;
- environment-based application settings;
- `GET /health` process-health contract;
- Pytest and Ruff verification; and
- reproducible uv lockfile and package build.

## Setup

From `apps/api`:

```bash
uv sync --locked
```

## Run

```bash
uv run uvicorn industrial_agent.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

The process-health endpoint is available at `http://127.0.0.1:8000/health`.

## Verify

```bash
uv run pytest
uv run ruff check .
uv build
```

## Planned v0.1 responsibilities

- conversation and message HTTP APIs;
- SQLite persistence and migrations;
- one OpenAI-compatible LLM adapter;
- configuration validation and explicit error handling; and
- backend tests.

## Non-responsibilities

LangGraph, RAG, MCP, manufacturing analytics, production tools, authentication,
streaming, and distributed deployment are outside v0.1.

## Dependency management

Backend metadata and runtime dependencies are declared in `pyproject.toml`.
Development tools are kept in a separate dependency group, and `uv.lock`
records the resolved environment.

## Current limitations

The API does not yet persist conversations, call an LLM, or expose
manufacturing data. The health endpoint reports API-process availability only.
