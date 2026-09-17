# ForgeAI

[![CI](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Production-oriented GitHub pull-request risk, review, and governance platform.**

ForgeAI combines a deterministic risk engine with bounded repository context, optional LLM planning, and an asynchronous control plane for persisted review workflows and governed automation. The core decision path remains usable without an external model, while model-assisted reasoning is constrained by typed inputs, context limits, secret redaction, and explicit fallback behavior.

> **Portfolio focus:** backend architecture + developer tooling + secure LLM integration + GitHub automation.

> **Control-plane build:** PostgreSQL persistence, Redis jobs, evidence ingestion, approval-gated automation, MCP-style tooling, and OpenTelemetry/Prometheus observability.

## Why ForgeAI

LLM-assisted code review can introduce a second class of risk: repository content must never silently become executable instructions for the review system. ForgeAI treats repository files as data, keeps the deterministic baseline independent of the LLM, and makes model-assisted reasoning an optional planning layer rather than a trusted decision-maker.

## Architecture

```text
GitHub Pull Request
        |
        v
FastAPI Control Plane
        |
        +--> PostgreSQL ---- review history / evidence / approvals / execution audit
        |
        +--> Redis ---------- durable review-job queue
        |
        +--> Review Worker -- deterministic analysis -> bounded context -> planner
        |                                      |
        |                                      +--> deterministic
        |                                      +--> OpenAI-compatible LLM
        |
        +--> Evidence API --- CodeQL / dependency-review SARIF
        |
        +--> Approval Gate -- explicit human approval
        |
        +--> Tool Gateway --- allowlisted GitHub Actions dispatch
                   |
                   +--> JSON-RPC /mcp gateway

Observability: OpenTelemetry tracing + Prometheus metrics
```

## Capabilities

### Deterministic review core

- Security, credential, infrastructure, data, dependency, test-impact, and change-size rules.
- Stable rule IDs and explainable 0–100 risk scoring.
- Critical findings and threshold breaches produce a review-required gate.
- No LLM is required for the baseline decision.

### Repository-aware assisted review

- Pull-request changed-file pagination.
- Head-SHA file retrieval.
- Bounded context selection and relevance ranking.
- Private-key and secret-value redaction.
- Repository content is treated as untrusted data and never executed.
- OpenAI-compatible planner with structured JSON parsing and deterministic fallback.

### Asynchronous control plane

`POST /v1/jobs` creates a persisted review job and enqueues it. The queue is Redis-backed when `REDIS_URL` is configured and falls back to an in-process queue for local development.

The worker persists state transitions:

`queued -> running -> succeeded | failed`

Review reports, plans, evidence, approvals, and action executions remain queryable after the worker finishes.

### CodeQL and dependency-review ingestion

`POST /v1/jobs/{job_id}/evidence/sarif?source=codeql` accepts SARIF-shaped analysis output. The same endpoint accepts `source=dependency-review`.

High or critical external evidence can raise the effective gate to `review_required`, even when the deterministic baseline was below the configured threshold.

### Human approval and governed automation

ForgeAI exposes an explicit approval state machine:

`pending -> approved | rejected`

Side-effecting tools cannot execute without an approved review job. The tool gateway allowlists workflow IDs through `ALLOWED_GITHUB_WORKFLOWS` and currently exposes `github.workflow_dispatch`.

### MCP-style tool gateway

`POST /mcp` supports JSON-RPC methods `tools/list` and `tools/call`. Tool calls are linked to a persisted review job and require an approved state before the GitHub Actions dispatch adapter is reached.

### Observability

- OpenTelemetry spans around review processing.
- Prometheus counters for started/completed jobs.
- Review-duration histogram.
- `GET /metrics` for Prometheus scraping.

## API

### Liveness and readiness

```text
GET /health
GET /ready
GET /metrics
```

### Synchronous review endpoints

```text
POST /v1/reviews
POST /v1/reviews/assisted
```

### Control-plane endpoints

```text
POST /v1/jobs
GET  /v1/jobs
GET  /v1/jobs/{job_id}
POST /v1/jobs/{job_id}/evidence
POST /v1/jobs/{job_id}/evidence/sarif?source=codeql
POST /v1/jobs/{job_id}/approval/approve
POST /v1/jobs/{job_id}/approval/reject
POST /v1/jobs/{job_id}/execute
GET  /v1/tools
POST /mcp
```

### `GET /docs`

Interactive OpenAPI documentation.

## Engineering controls

### Separation of concerns

The risk engine consumes a typed pull-request snapshot. GitHub HTTP behavior is isolated behind an adapter, while review planning is isolated behind a planner interface.

### Untrusted repository content

Repository files are handled as data, not instructions. Context is bounded before planning, common secret values are redacted, and model-assisted planning is optional.

### Deterministic fallback

An external model enhances the review workflow but is not the sole dependency for the baseline review decision.

### Bounded upstream access

Changed-file retrieval is paginated with a maximum page count. Context retrieval is limited by both file count and characters per file.

### Approval-gated side effects

Review analysis, external evidence, human authorization, and tool execution are separate control-plane stages. An approved state is persisted before a side-effecting GitHub Actions dispatch can execute.

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Persistence | SQLAlchemy async, SQLite local, PostgreSQL production |
| Queue | asyncio local queue, Redis production |
| GitHub | GitHub API integration |
| Review engine | Deterministic rules + typed models |
| LLM | OpenAI-compatible provider |
| Evidence | SARIF / CodeQL / dependency-review |
| Quality | Pytest, Ruff, evaluation harness |
| Security | Secret redaction, prompt-injection boundary, CodeQL |
| Observability | OpenTelemetry + Prometheus |
| Automation | GitHub Actions + approval gate + MCP-style tool gateway |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Repository structure

```text
forgeai/
├── src/forgeai/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── control_models.py
│   ├── db.py
│   ├── db_models.py
│   ├── repository.py
│   ├── queue.py
│   ├── evidence.py
│   ├── evidence_ingest.py
│   ├── observability.py
│   ├── tool_gateway.py
│   ├── services/
│   │   ├── analyzer.py
│   │   ├── context.py
│   │   ├── evaluator.py
│   │   ├── github_client.py
│   │   ├── planner.py
│   │   ├── review_engine.py
│   │   ├── review_service.py
│   │   └── risk.py
│   └── worker.py
├── tests/
├── evals/cases.jsonl
├── scripts/run_eval.py
├── docs/control-plane.md
├── .github/workflows/ci.yml
├── .github/workflows/codeql.yml
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Local development

Python 3.11+ is supported. Docker Compose provides the full control-plane stack.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

For the full service topology:

```bash
docker compose up --build
```

Run quality checks:

```bash
pytest
ruff check src tests scripts
python scripts/run_eval.py
```

Run a standalone Redis worker:

```bash
python -m forgeai.worker
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `GITHUB_TOKEN` | GitHub API token | empty |
| `RISK_GATE_THRESHOLD` | Baseline risk threshold | `60` |
| `HTTP_TIMEOUT_SECONDS` | GitHub API timeout | `15` |
| `CONTEXT_MAX_FILES` | Context file bound | `5` |
| `CONTEXT_MAX_CHARS` | Context character bound | `12000` |
| `LLM_BASE_URL` | OpenAI-compatible API base URL | empty |
| `LLM_API_KEY` | LLM API key | empty |
| `LLM_MODEL` | Model name | `gpt-4.1-mini` |
| `LLM_TIMEOUT_SECONDS` | LLM timeout | `30` |
| `DATABASE_URL` | SQLAlchemy async database URL | `sqlite+aiosqlite:///./forgeai.db` |
| `REDIS_URL` | Redis connection URL; empty enables local queue | empty |
| `ALLOWED_GITHUB_WORKFLOWS` | JSON list of workflow IDs permitted for dispatch | `["ci.yml"]` |

For production, use PostgreSQL through an async SQLAlchemy URL such as `postgresql+asyncpg://...` and run the worker as a separate service.

## Security model

The control plane separates analysis from execution. Repository data is bounded and redacted before optional model use. External analysis is evidence rather than direct authority. Side-effecting automation is allowlisted and requires an explicit persisted approval state. Execution history is stored in PostgreSQL/SQLite so the control plane has an auditable record of what was requested.

## Evaluation

The deterministic analyzer uses versioned cases in `evals/cases.jsonl` and reports precision, recall, and exact-match coverage through `scripts/run_eval.py`. CI runs linting, tests, the evaluation benchmark, and a Docker build.

## Next engineering layer

- Repository-wide semantic retrieval with embeddings.
- Adversarial prompt-injection and tool-abuse benchmark suite.
- OTLP exporter and trace correlation across API, worker, and tool execution.
- Idempotency keys and durable dead-letter handling for review jobs.
- GitHub App/webhook ingestion for fully event-driven review workflows.

## License

MIT
