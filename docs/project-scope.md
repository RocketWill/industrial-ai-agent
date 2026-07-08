# Project Scope

## Positioning

Industrial AI Agent for Semiconductor Manufacturing is an independent,
educational portfolio project. It explores how a stateful AI agent can combine
manufacturing-domain models, production-data tools, equipment-document
retrieval, and explicit workflow orchestration to answer traceable industrial
questions.

All equipment interfaces, documents, datasets, alarm codes, and evaluation
scenarios will be synthetic and created specifically for this repository.

## Ownership and public-release boundary

This project is not a company product or a sanitized copy of an existing
system. It must be independently explainable, executable, and publishable.

The repository must not contain or imply:

- employer, customer, or proprietary product identities;
- copied source code, Git history, screenshots, documents, or schemas;
- internal URLs, IP addresses, APIs, deployment architecture, or credentials;
- real equipment names, factory data, production records, or customer data; or
- unauthorized work product or confidential implementation details.

General software-engineering knowledge may inform the design, but every
artifact in this repository must be independently authored.

## Intended capabilities

The planned system will eventually:

1. persist conversations and structured equipment/time-range context;
2. query synthetic equipment and production records;
3. calculate yield, throughput, status, and defect metrics in deterministic
   Python code;
4. retrieve fictional manuals, SOPs, and alarm guides with citations;
5. route requests to document, production, or combined workflows;
6. validate evidence and handle missing data, timeouts, invalid formats, and
   retries safely;
7. display execution traces, tool calls, sources, errors, and retry activity;
   and
8. evaluate agent behavior with fixed synthetic scenarios.

## Evidence and answer boundaries

Responses must distinguish:

- document retrieval results;
- structured production records;
- programmatically calculated metrics;
- model-generated interpretation; and
- uncertainty or insufficient evidence.

The system must not invent equipment state, production values, yield, defects,
or causal explanations when evidence is absent. Numeric manufacturing logic
belongs in deterministic domain code rather than an LLM.

## Current milestone boundary

The active milestone is **v0.1 — Full-stack Foundation**.

The current implementation includes the FastAPI application, explicit SQLite
migrations, Conversation and Message persistence, and one synchronous
OpenAI-compatible chat adapter. The Message API stores a user Message, requests
one assistant response, and persists that response when the compatible service
succeeds.

The React application provides API-process health, conversation navigation,
message history, synchronous exchanges, and critical interaction tests.
Streaming is implemented separately in v0.1.1 so its transport and persistence
boundary can be tested without changing the v0.1 synchronous contract.

The following are deliberately excluded from v0.1:

- LangGraph orchestration;
- manufacturing domain models and datasets;
- production-data tools;
- RAG and vector storage;
- MCP;
- authentication, multi-tenancy, and complex authorization;
- streaming, Redis, microservices, and high-availability deployment; and
- Docker or cluster infrastructure.

Streaming is implemented in v0.1.1 after the synchronous React conversation
workflow was verified. Keeping it in a separate milestone allowed the
transport contract, cancellation and disconnect behavior, partial response
handling, and persistence boundary to be specified and tested together.

## Publication safety

Only placeholder configuration and synthetic artifacts may be committed.
Secrets belong in ignored local environment files. If the provenance or public
safety of an artifact is uncertain, it must remain outside the repository
until reviewed.

## Status vocabulary

Project documentation uses these labels:

- **Implemented** — supported by working code and relevant verification
- **Experimental** — working exploration without a stable contract
- **In Progress** — actively being built and not yet accepted
- **Planned** — not implemented
- **Deprecated** — retained temporarily but no longer recommended
