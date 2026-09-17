# ForgeAI

[![CI](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Production-oriented GitHub pull-request risk, review, and governance platform.**

ForgeAI combines a deterministic risk engine with bounded repository context, optional LLM-assisted planning, and an asynchronous control plane for persisted review workflows and governed automation.

> **Portfolio focus:** Python backend architecture · developer tooling · secure LLM integration · GitHub automation.

## Problem

LLM-assisted code review creates a new trust boundary: repository content must be treated as untrusted data, while the baseline risk decision should remain deterministic and reproducible.

ForgeAI separates those concerns:

```text
GitHub PR
   ↓
Signed webhook → persisted delivery
   ↓
Deterministic risk analysis
   ↓
Bounded repository context
   ↓
Optional LLM planning
   ↓
Evidence + approval gate
   ↓
Allowlisted automation
```

## Current capabilities

### Deterministic review engine

- Security, credential, infrastructure, data, dependency, test-impact, and change-size rules.
- Stable rule IDs with explainable 0–100 risk scoring.
- Critical findings and threshold breaches can require review.
- Baseline analysis does not depend on an external LLM.

### Repository-aware review

- Pull-request changed-file pagination and head-SHA retrieval.
- Bounded semantic repository retrieval with policy-aware access.
- Private-key and secret-value redaction.
- Repository content treated as data, never executed.
- Optional OpenAI-compatible planner with structured output and deterministic fallback.

### Control plane

- PostgreSQL persistence with Alembic migrations.
- Redis-backed review queue with local in-process fallback.
- Signed GitHub webhook ingestion with idempotent delivery tracking.
- Durable retry/dead-letter handling for dispatch failures.
- Evidence ingestion for CodeQL/dependency-review SARIF.
- Approval-gated side effects with operator RBAC.
- JSON-RPC `/mcp` gateway with an allowlisted GitHub Actions dispatch adapter.

### Security and evaluation

- HMAC SHA-256 webhook verification.
- Prompt-injection and tool-abuse boundaries.
- Versioned deterministic evaluation cases.
- Versioned adversarial security benchmark corpus.
- Structured fallback behavior when the model is unavailable.

### Observability

- OpenTelemetry tracing and OTLP export.
- Prometheus metrics at `/metrics`.
- Review-duration and job lifecycle telemetry.

## Technology stack

| Area | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy async |
| Data | PostgreSQL, SQLite local, Alembic |
| Queue | Redis, asyncio local queue |
| GitHub | GitHub API, signed webhooks |
| AI | OpenAI-compatible LLM, bounded retrieval |
| Security | HMAC, secret redaction, RBAC, CodeQL |
| Observability | OpenTelemetry, OTLP, Prometheus |
| Quality | PyTest, Ruff, evaluation harness |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Repository structure

```text
forgeai/
├── src/forgeai/
│   ├── services/          # review, risk, retrieval, planning
│   ├── webhook.py         # signed GitHub webhook boundary
│   ├── worker.py          # asynchronous review worker
│   ├── evidence*.py       # evidence ingestion
│   ├── tool_gateway.py    # approval-gated automation
│   └── observability.py   # traces and metrics
├── tests/
├── evals/cases.jsonl
├── scripts/run_eval.py
├── docs/
├── migrations/
├── .github/workflows/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Local development

```bash
git clone https://github.com/AloneRider-pixel/forgeai.git
cd forgeai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Full control-plane stack:

```bash
docker compose up --build
```

Quality checks:

```bash
pytest
ruff check src tests scripts
python scripts/run_eval.py
```

Interactive API docs are available at `/docs`.

## Security model

ForgeAI keeps ingestion, analysis, evidence, authorization, and execution as separate stages. GitHub webhook authenticity is verified before event parsing; repository context is bounded and redacted before optional model use; external analysis is treated as evidence; and side-effecting automation requires explicit persisted approval and RBAC authorization.

## Evaluation

Deterministic review cases are versioned in `evals/cases.jsonl`. The repository also contains a separate adversarial corpus for prompt-injection and tool-abuse testing. Published performance numbers should be tied to a specific dataset version, methodology, and reproducible run.

## Roadmap

- Broader provider and repository-language adapters.
- Expanded benchmark coverage with published methodology.
- Multi-tenant deployment examples and additional policy controls.
- Deeper latency and cost telemetry for model-assisted paths.

## License

MIT
