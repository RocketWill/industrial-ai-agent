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

The v0.1 foundation, streaming v0.1.1, Industrial Chat Workspace UI v0.1.2,
and minimal LangGraph orchestration v0.2 are implemented. v0.3 Manufacturing
Domain remains in progress with its deterministic AOI analysis slice
implemented. v0.4 Production Data Tools is the active milestone: the first
tool contract, OpenAI-compatible tool-call protocol, workspace-context
resolution, synchronous grounded answers, SSE tool events, and current-exchange
structured evidence display are implemented. Persisted evidence and provider
token streaming after tool execution remain open.

Architecture notes and engineering decisions should be added only when the
corresponding code or approved decision exists. Local PRDs, specs, and plans
follow the dated formats under `docs/superpowers/` and are not part of the
public repository.
