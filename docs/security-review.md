# Security Review

This is a bounded review of the local, single-user development application. It
is not a penetration test, security certification, vulnerability-response
policy, or approval to expose the service publicly.

## Threat model and deployment boundary

The FastAPI and Vite development processes are intended for localhost use.
There is no authentication, authorization, rate limiting, tenant isolation,
TLS termination, hardened session boundary, or production deployment stack.
Do not bind this application to an untrusted network or use it for production
equipment and records.

Model output is untrusted interpretation. The application does not issue
equipment commands, and deterministic tools read repository-owned synthetic
data. Real production data, equipment exports, credentials, and proprietary
documents are outside the allowed data boundary.

## Secrets and external model services

Secrets belong in ignored local environment files. `LLM_API_KEY` is read by the
backend and must not be placed in `VITE_*` variables, screenshots, fixtures, or
documentation. When the configured OpenAI-compatible endpoint is external,
conversation text and retrieved local document excerpts may leave the local
machine. The operator is responsible for reviewing that service's data policy.

## Local storage and uploads

SQLite stores conversations, messages, workspace context, and canonical
Evidence Snapshots on local disk. Conversation deletion permanently removes its
messages and snapshots. Snapshots may retain excerpts from a local upload after
that upload is deleted, because historical evidence records what supported the
completed answer. Model Working Notes are not persisted.

The Documents API accepts one UTF-8 `.md` file up to 1 MiB, validates it before
atomically replacing the candidate corpus, protects built-in documents, and
allows local uploads to be deleted. Upload storage is Git-ignored. There is no
malware scanner, content moderation, per-user ownership, quota system, or
multi-user isolation.

Document text is untrusted input. Retrieved instructions can influence a model
prompt, so citations identify evidence but do not make the content safe or
authoritative. The current workflow constrains numeric and citation claims in
application code; it does not claim complete prompt-injection resistance.

## MCP boundary

The MCP server is an independent local stdio process exposing three strict,
deterministic manufacturing tools. It does not provide HTTP transport,
authentication, model access, document search, workspace context, or live data.
Its safety depends on the local client and process boundary remaining trusted.

## Dependency observations

Audits were last checked against the 2026-08-18 locked installations.

- `npm audit --omit=dev` reported two moderate production dependency findings:
  DOMPurify through XMarkdown and Mermaid through Ant Design X. It reported no
  high or critical production finding.
- The full npm tree additionally reported high and critical development-tool
  findings, including Vitest UI and Vite development-server exposure. CI runs
  `vitest run` and the production build; it does not start Vitest UI. Local
  development servers must still remain on trusted interfaces.
- The installed Python audit reported moderate LangGraph-family advisories.
  Their described paths require persistent checkpointers and resume, a cache
  backend, or LangGraph SDK resource calls. This application uses none of those
  paths.

These exposure notes do not mean the dependencies are vulnerability-free.
Automatic or major-version fixes were not applied because they would change
the validated dependency and behavior boundary. Findings should be reassessed
before any dependency upgrade or deployment change.

## Repository publication review

A manual redacted scan of the current tree and reachable Git history found no
credential pattern, private key, production dataset, internal URL, previously
committed environment file, database, or unusually large blob. Local planning
documents, uploads, databases, build artifacts, and dependency directories are
ignored. Dedicated tools such as gitleaks or trufflehog were not available, so
this result must not be described as a formal secret-scanner pass.

## Residual risks

- no authentication or multi-user isolation;
- untrusted Markdown may be sent to the configured model service;
- model and document prompt injection is reduced by deterministic evidence
  boundaries, not eliminated;
- local database and uploaded files rely on operating-system access control;
- development servers and MCP clients are trusted local processes; and
- dependency advisories remain and require periodic reassessment.
