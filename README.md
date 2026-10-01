# ForgeAI

[![CI](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Production-oriented GitHub pull-request risk, review, and governance platform.

ForgeAI keeps the baseline risk decision deterministic while using optional model-assisted planning, bounded repository context, persisted workflows, and approval-gated automation.

## Core architecture

```text
GitHub PR
   ↓
Signed webhook / persisted delivery
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

## Capabilities

- Security, credential, infrastructure, data, dependency, test-impact, and change-size analysis.
- Stable rule IDs and explainable risk factors.
- Pull-request-aware repository retrieval with bounded context and secret redaction.
- PostgreSQL persistence, Alembic migrations, and Redis-backed review queues.
- Signed GitHub webhook ingestion with idempotent delivery tracking.
- CodeQL/dependency-review evidence ingestion.
- Approval-gated side effects with operator RBAC.
- OpenTelemetry and Prometheus instrumentation.
- Versioned deterministic and adversarial evaluation corpora.

## Stack

| Area | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy |
| Data | PostgreSQL, SQLite, Alembic |
| Queue | Redis / asyncio |
| GitHub | REST API, signed webhooks |
| AI | OpenAI-compatible model, bounded retrieval |
| Security | HMAC, redaction, RBAC, CodeQL |
| Quality | Pytest, Ruff, evaluation harness |
| Delivery | Docker, GitHub Actions |

## Repository layout

```text
src/forgeai/
  services/         # analysis, risk, retrieval, planning
  webhook.py        # signed GitHub webhook boundary
  worker.py         # asynchronous review worker
  evidence*.py      # security evidence ingestion
  tool_gateway.py   # approval-gated automation
  observability.py  # telemetry
tests/
evals/
scripts/
migrations/
docs/
```

## Quick start

```bash
git clone https://github.com/AloneRider-pixel/forgeai.git
cd forgeai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Docker:

```bash
docker compose up --build
```

## Verification

```bash
ruff check src tests scripts migrations
pytest --cov=forgeai --cov-report=term-missing
alembic upgrade head
python scripts/run_eval.py --output artifacts/benchmark.json
python scripts/run_security_eval.py --output artifacts/security.json
python scripts/verify_evidence.py --benchmark artifacts/benchmark.json --security artifacts/security.json
```

These commands mirror the repository CI gates.

## Security model

Repository content, pull-request text, logs, and model output are untrusted data. Webhook authenticity is verified before processing, retrieval is bounded and redacted, and side-effecting automation requires explicit persisted approval and authorization.

## Evaluation integrity

Risk scores and evaluation results are meaningful only in the context of their corpus, methodology, environment, and version. Synthetic/adversarial fixtures are engineering evidence, not production benchmark claims.

See [Evidence Policy](docs/evidence-policy.md).

## Roadmap

- Broader repository/language adapters.
- More benchmark coverage with published methodology.
- Multi-tenant policy controls.
- Deeper model latency/cost telemetry.

## Review path

Start with [architecture](docs/architecture.md), [next layer](docs/next-layer.md), and [SECURITY.md](SECURITY.md). Preserve deterministic policy decisions and approval gates when changing agent behavior.

## Maintenance standard

Keep repository content untrusted, actions immutable, policy decisions deterministic, and execution authority separate from analysis.

## License

MIT
