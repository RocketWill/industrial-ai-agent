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

The active milestone is **v0.5 — Self-built RAG**. The v0.1 foundation,
v0.1.1 streaming extension, v0.1.2 workspace extension, and v0.2 minimal
LangGraph orchestration are implemented, including clean-environment
verification. v0.3 Manufacturing Domain is implemented; throughput is
explicitly deferred until a later dataset and unit contract can support it. Its
domain slices provide deterministic production summaries and defect
distributions, explicit equipment-state
intervals, point-in-time status lookup, and one fictional AOI wafer-inspection
dataset.

The current backend includes explicit SQLite migrations, Conversation and
Message persistence, synchronous and streaming OpenAI-compatible chat flows,
conversation-bound workspace context, a deterministic fictional device
catalog, and synchronous plus SSE production-summary, defect-distribution, and
equipment-status tool flows. The current document slice builds an explicit
three-document fictional Markdown corpus and exposes deterministic local
retrieval through synchronous and SSE `search_documents` flows. The React
application provides API-process health, conversation and message workflows,
streaming controls, responsive conversation navigation, draft-based context
editing, Markdown assistant rendering, and current-exchange tool stages and
evidence for focused English production-summary, defect-distribution, and
equipment-status terms, plus current-exchange fictional document sources.

Streaming and the refined workspace are recorded as completed v0.1.1 and
v0.1.2 extensions.

The following are deliberately excluded from v0.1:

- LangGraph orchestration;
- manufacturing domain models and datasets;
- production-data tools;
- RAG and vector storage;
- MCP;
- authentication, multi-tenancy, and complex authorization;
- Redis, microservices, and high-availability deployment; and
- Docker or cluster infrastructure.

Streaming is outside the original v0.1 contract but implemented in v0.1.1.
Keeping it separate allowed client cancellation, partial-response handling,
and the completed-response persistence boundary to be specified together.

The active implementation milestone is v0.5. It now includes stable
section-local citations, bounded paragraph- and list-aware chunks,
deterministic feature-hashing embeddings, an in-memory cosine index, a fixed
lexical eligibility gate, and a 12-scenario retrieval fixture. It uses no
external embedding service. A registry-only API and read-only Drawer expose
the complete cited document. Document management, multi-tool turns, and
persisted evidence remain outside the current boundary.

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
