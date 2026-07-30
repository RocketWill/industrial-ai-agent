# API

## Purpose

This directory will contain the FastAPI backend for v0.1.

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

Backend metadata will live in this directory's `pyproject.toml`. Runtime and
development dependencies will be declared separately when the first executable
backend change is introduced. No Python package has been selected or installed
in the repository baseline.

## Current status

**Planned** — no backend code or dependencies exist yet.
