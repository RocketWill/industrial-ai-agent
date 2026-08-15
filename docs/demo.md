# Combined Evidence Demo

Combined Evidence is the primary v1.0 demonstration. It tests the seam that is
hardest to fake: one exchange must preserve deterministic production values,
retrieved document sources, their separate failure states, and the boundary
between a possible relationship and a verified cause.

## Setup

1. Start the API and web client by following the root README.
2. Configure an OpenAI-compatible model with `LLM_MODEL`. Do not place a key in
   browser configuration or commit it to the repository.
3. Create a conversation and save this synthetic workspace context:

   | Field | Value |
   | --- | --- |
   | Device | `AOI-WAFER-01` |
   | Lot | `LOT-DEMO-01` |
   | Time range | `Last 4 hours` |

4. Submit this prompt:

   > For AOI-WAFER-01 and LOT-DEMO-01 over the last 4 hours, summarize the
   > production evidence and search the fictional documents for relevant alarm
   > or maintenance guidance. Keep recorded facts, calculations, document
   > guidance, and possible interpretation separate. Do not claim a cause.

## Acceptance invariants

Exact model prose is not part of the contract. Check these observable results:

- the route selects exactly one manufacturing evidence path plus documents;
- manufacturing runs before Document Search;
- the production result identifies its synthetic source and deterministic
  calculation boundary;
- every displayed document source includes a title, section, excerpt, stable
  source ID, and repository-relative path;
- manufacturing and document evidence appear in separate regions;
- the answer does not invent an unavailable value or citation;
- any cross-evidence relationship is framed as a possibility, not a verified
  cause; and
- the assistant message is persisted only after a complete non-empty answer.

## Observable outcomes

| Outcome | What should appear |
| --- | --- |
| Happy path | Both evidence regions succeed and the final answer passes numeric, citation, and causal-claim validation. |
| Degraded | Evidence is available, but model synthesis fails or is rejected; a deterministic safe response retains valid evidence. |
| Partial failure | One evidence path fails while the other valid path remains visible with an explicit failure state. |
| Model unavailable | The API process remains reachable, while the message request reports that the assistant is temporarily unavailable. |

Degraded and partial-failure output must not be presented as a successful
happy-path observation.

## Accepted local observation

The v1.0 screenshot observation is pending. When accepted, this section will
record only the run date, model identifier, OpenAI-compatible adapter type, and
non-sensitive timeout. It will not record a key, private endpoint, private path,
or local hardware claim.

Two 2026-08-15 local candidates were rejected rather than captured as release
screenshots. `llama3.1:8b` retrieved evidence but did not produce a combined
answer that passed the synthesis boundary. `deepseek-r1:7b` did not complete
the manufacturing tool path. Both observations correctly appeared as degraded
or partial failure, so neither satisfies the happy-path screenshot contract.
