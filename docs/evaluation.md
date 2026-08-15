# Evaluation

The repository includes a deterministic offline evaluator for routing,
manufacturing tools, retrieval, citations, failure handling, and answer
grounding. It is designed to catch contract regressions without depending on a
model service.

## Run it

From `apps/api`:

```bash
uv sync --locked
uv run industrial-agent-eval
```

The command validates the package-owned fixture, runs all 45 English and
Traditional Chinese scenarios, prints each dimension separately, and exits
non-zero if a threshold fails. It writes a typed JSON result to
`.artifacts/evaluation/latest.json`; `.artifacts/` is intentionally ignored by
Git.

## Latest result

The fresh 2026-08-15 local run passed all 45 scenarios:

| Dimension | Result |
| --- | ---: |
| Route | 33 / 33 |
| Tool selection | 16 / 16 |
| Argument resolution | 4 / 4 |
| Evidence parity | 13 / 13 |
| Retrieval top-one | 9 / 9 |
| Retrieval top-three | 12 / 12 |
| Citation | 4 / 4 |
| Safe failure | 9 / 9 |
| Unsupported-claim rejection | 5 / 5 |
| Retry or fallback | 2 / 2 |

The fixture digest was
`bb803165a3cd9445438302f7dab33e56377e2fe1d0a3ce156e4edf2120c44cc3`.
The runner recorded `2026-08-15T02:14:28.630691Z` through
`2026-08-15T02:14:28.675477Z`; this roughly 44.8 ms interval is one local
observation, not a release threshold. Per-scenario stage timings remain in the
ignored raw artifact.

## What this result means

The evaluator executes existing routing, native tool, combined workflow,
retrieval, evidence, and answer-validation seams. It checks explicit expected
outcomes rather than grading free-form prose. That makes failures explainable:
a route, citation, numeric claim, retry, or fallback assertion fails on its own
dimension instead of disappearing into a composite score.

## What it does not mean

This suite is not an LLM judge, semantic answer-quality benchmark, production
benchmark, latency service-level objective, or external telemetry system. It
does not call a live provider or exercise the browser and HTTP layers. Recorded
elapsed times are local diagnostic observations, not performance guarantees or
release thresholds.
