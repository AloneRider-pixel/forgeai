# ForgeAI — Pull-Request Risk & Governance Platform

[![CI](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Production-oriented platform for pull-request risk analysis, evidence collection, reviewer guidance, governance, and approval-gated automation.

ForgeAI deliberately keeps policy decisions deterministic while allowing bounded model assistance for planning and repository context.

## Core flow

```text
GitHub PR
   ↓
Signed webhook
   ↓
Deterministic risk analysis
   ↓
Bounded repository context
   ↓
Optional model planning
   ↓
Evidence + approval gate
   ↓
Allowlisted automation
```

## Capabilities

- Security, credential, infrastructure, dependency, test-impact, and change-size analysis.
- Stable rule IDs and explainable risk factors.
- Bounded repository retrieval with secret redaction.
- Signed webhook ingestion with persisted delivery idempotency.
- PostgreSQL persistence, migrations, and Redis-backed queues.
- CodeQL/dependency-review evidence ingestion.
- Operator RBAC and approval-gated side effects.
- OpenTelemetry/Prometheus instrumentation.
- Deterministic and adversarial evaluation corpora.

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

## Repository map

```text
src/forgeai/
  services/
  webhook.py
  worker.py
  evidence*.py
  tool_gateway.py
  observability.py
tests/
evals/
scripts/
migrations/
docs/
.github/workflows/
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

## Security model

Pull-request text, repository files, logs, dependency metadata, and model output are untrusted. Verify webhook authenticity before processing, bound and redact retrieved data, and keep side effects behind explicit persisted approval and authorization.

## Evaluation integrity

Risk scores are meaningful only in the context of their corpus, methodology, environment, and version. Synthetic/adversarial fixtures are engineering evidence, not production outcome claims.

See [docs/evidence-policy.md](docs/evidence-policy.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Control plane](docs/control-plane.md)
- [Assisted review](docs/assisted-review.md)
- [Next layer](docs/next-layer.md)
- [Security](SECURITY.md)

## Roadmap

Broader repository/language adapters, additional benchmark coverage, multi-tenant policy controls, and deeper cost/latency telemetry.

## License

MIT
