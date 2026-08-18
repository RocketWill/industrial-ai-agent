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
   | Lot | `LOT-DEMO-001` |
   | Time range | `Last 4 hours` |

4. Submit this prompt:

   > For AOI-WAFER-01 and LOT-DEMO-001 over the last 4 hours, summarize the
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
- the answer does not invent a manufacturing value or document source ID;
- inline source IDs are optional because the structured Sources region owns
  traceability; if the answer includes an ID, it matches a returned source;
- any cross-evidence relationship is framed as a possibility, not a verified
  cause and states that validation is still required;
- the answer does not infer equipment, process, or operating status from
  evidence that does not record that status; and
- the assistant message is persisted only after a complete non-empty answer.

## Observable outcomes

| Outcome | What should appear |
| --- | --- |
| Happy path | Both evidence regions succeed and the final answer passes manufacturing-value, optional-source-ID, causal, and operational-claim validation. |
| Degraded | Evidence is available, but model synthesis fails or is rejected; a deterministic safe response retains valid evidence. |
| Partial failure | One evidence path fails while the other valid path remains visible with an explicit failure state. |
| Model unavailable | The API process remains reachable, while the message request reports that the assistant is temporarily unavailable. |

Degraded and partial-failure output must not be presented as a successful
happy-path observation.

## Accepted local observation

The accepted local observation ran on 2026-08-15 with `qwen3:14b` through the
OpenAI-compatible adapter and a 120-second timeout. It includes no key, private
endpoint, private path, or local hardware claim. Both evidence paths completed,
the final synthesis passed validation, and the assistant response was
persisted. The root README includes the desktop and 390 px screenshots from
this run.

Two 2026-08-15 local candidates were rejected rather than captured as release
screenshots. `llama3.1:8b` retrieved evidence but did not produce a combined
answer that passed the synthesis boundary. `deepseek-r1:7b` did not complete
the manufacturing tool path. Both observations correctly appeared as degraded
or partial failure, so neither satisfies the happy-path screenshot contract.

A later `qwen3:14b` observation exposed and corrected an invalid demo lot ID.
With `LOT-DEMO-001`, both evidence paths succeeded: the deterministic summary
reported 400 inspected wafers and 92.50% yield, and Document Search returned
stable fictional citations. The model's final synthesis still did not pass the
then-current combined grounding validator, so this candidate was also rejected.
That observation led to a narrower contract: deterministic manufacturing
claims remain strict, while formatting numbers and omitted inline citations no
longer cause an otherwise grounded answer to fail. A later run with the revised
contract produced the accepted observation recorded above.

## v2.0 reload and Working Notes observation

The final v2.0 browser acceptance used an independently created deterministic
OpenAI-compatible fixture and repository-owned synthetic data. A completed
Production Summary reappeared under its assistant message after desktop and
390 px reloads. The same run displayed a Combined partial failure, a retained
source excerpt from a deleted synthetic upload, a legacy message without a
snapshot, and an unsupported snapshot version without hiding its message.

When the fixture supplied final-answer reasoning, Model Working Notes opened
during generation, collapsed when the Final Answer began, and could be reopened.
Truncation remained plain text, and cancellation produced an Interrupted state.
Reload removed the notes while preserving completed assistant text and Evidence
Snapshots. Provider wording and the presence of reasoning are not release
assertions.
