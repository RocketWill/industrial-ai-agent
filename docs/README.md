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

Milestones through v0.9 are implemented. The current boundary includes the
full-stack conversation foundation, deterministic manufacturing tools, local
document retrieval, bounded routing, guided historical choices, local stdio
MCP, formal offline evaluation, and one combined manufacturing-plus-document
workflow. Evidence remains current-exchange-only, and production data,
authentication, causal analysis, and remote deployment remain out of scope.

Architecture notes and engineering decisions should be added only when the
corresponding code or approved decision exists. Local PRDs, specs, and plans
follow the dated formats under `docs/superpowers/` and are not part of the
public repository.
