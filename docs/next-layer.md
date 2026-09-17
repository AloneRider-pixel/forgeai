# ForgeAI governance layer

This layer adds four production controls around the existing event-driven review plane.

## Semantic retrieval

`POST /v1/retrieval/index` indexes repository blobs into PostgreSQL. When an OpenAI-compatible embeddings endpoint is configured, document and query vectors are stored and ranked by cosine similarity. Without embeddings, the service uses a deterministic lexical fallback so local development remains functional.

`POST /v1/retrieval/search` returns ranked repository context with the retrieval mode attached to every hit.

## RBAC

API access can be enabled with `AUTH_REQUIRED=true`. Tokens are never persisted in configuration; `API_KEY_ROLES` contains SHA-256 token hashes mapped to `reader`, `reviewer`, and `operator` roles.

Reader access covers read-only review and retrieval APIs. Reviewer access covers security evidence and approval decisions. Operator access covers tool execution, MCP calls, and repository indexing.

## Adversarial evaluation

`evals/security_cases.json` is a small regression corpus covering instruction override, secret exfiltration, shell/tool abuse, policy bypass, system-prompt extraction, and a benign control. CI runs this benchmark on every pull request.

## Database migrations

Alembic is the schema authority for deployments. Containerized environments disable automatic table creation and run `alembic upgrade head` in a dedicated migration service before API and worker processes start. SQLite auto-create remains available for local tests.

## Trace correlation

ForgeAI exports traces through OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is configured. Review spans carry `job.id`, repository, pull-request number, and trigger source so an asynchronous review can be correlated across the worker boundary.
