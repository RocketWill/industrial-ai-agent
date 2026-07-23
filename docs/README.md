# Documentation

The documentation is organized by responsibility so that milestone plans do
not become feature inventories and the root README does not duplicate detailed
contracts.

## Start here

1. [Project scope](project-scope.md) defines ownership, publication safety,
   evidence boundaries, and the active milestone boundary.
2. [Implementation status](implementation-status.md) records behavior supported
   by current code and tests, together with known limits.
3. [Roadmap](roadmap.md) defines milestone order, acceptance state, and planned
   work.
4. [API guide](../apps/api/README.md) contains backend setup, configuration,
   endpoint behavior, and verification commands.
5. [Web guide](../apps/web/README.md) contains frontend setup, interaction
   behavior, and verification commands.

## Status

The v0.1 foundation and its streaming and workspace extensions are implemented,
along with v0.2 LangGraph orchestration, v0.3 Manufacturing Domain, and v0.4
Production Data Tools. v0.5 Self-built RAG is active. Its first slice parses one
fictional Markdown alarm guide, builds deterministic local vectors, retrieves
sources through synchronous and SSE tool flows, and renders current-exchange
citation metadata. Broader ingestion, retrieval evaluation, source viewing,
and persisted evidence remain open.

Architecture notes and engineering decisions should be added only when the
corresponding code or approved decision exists. Local PRDs, specs, and plans
follow the dated formats under `docs/superpowers/` and are not part of the
public repository.
