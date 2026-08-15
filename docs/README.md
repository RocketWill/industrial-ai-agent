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
4. [Architecture](architecture.md) describes current runtime boundaries and
   the Combined Evidence sequence.
5. [Demo](demo.md) defines the primary local workflow and its observable
   acceptance invariants.
6. [Evaluation](evaluation.md) records the deterministic 45-scenario suite.
7. [Security review](security-review.md) records the local threat model,
   dependency observations, publication audit, and residual risks.
8. [API guide](../apps/api/README.md) contains backend setup, configuration,
   endpoint behavior, and verification commands.
9. [Web guide](../apps/web/README.md) contains frontend setup, interaction
   behavior, and verification commands.

## Status

Milestones through v0.9 are implemented. v1.0 release work is In Progress. The
current boundary includes the
full-stack conversation foundation, deterministic manufacturing tools, local
document retrieval, bounded routing, guided historical choices, local stdio
MCP, formal offline evaluation, and one combined manufacturing-plus-document
workflow. Evidence remains current-exchange-only, and production data,
authentication, causal analysis, and remote deployment remain out of scope.
Local deterministic checks pass, while screenshots, final clean-copy and code
review, publication acceptance, and remote CI remain release gates.

Architecture notes and engineering decisions should be added only when the
corresponding code or approved decision exists. Local PRDs, specs, and plans
follow the dated formats under `docs/superpowers/` and are not part of the
public repository.
