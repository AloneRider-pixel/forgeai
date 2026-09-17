# ForgeAI — AI Software Engineering Platform

ForgeAI is a production-oriented pull-request review platform for engineering organizations. It turns a GitHub pull request into a structured risk report using deterministic rules first, with explicit extension points for AI-assisted reasoning, security tooling, repository context, and controlled automation.

The goal is not to build another chat wrapper. ForgeAI models review as an auditable engineering workflow: ingest change metadata, classify risk, explain the evidence, apply policy, and expose a stable API that can later drive CI/CD and human approval workflows.

## What exists today

```text
GitHub Pull Request
        |
        v
   FastAPI API
        |
        v
  GitHub Adapter ---- retry / validation / pagination
        |
        v
 Deterministic Rule Engine
        |
        +---- security surface
        +---- credential / key material
        +---- infrastructure / deployment
        +---- data / migration
        +---- dependency changes
        +---- missing visible tests
        +---- large change surface
        |
        v
    Risk Engine
        |
        +---- 0–100 score
        +---- severity-aware policy gate
        +---- rule-level evidence
        |
        v
 Typed Review Report
```

### Current capabilities

- GitHub pull-request metadata and changed-file retrieval.
- Defensive upstream parsing with explicit API errors.
- Retry handling for transient GitHub/API failures.
- Paginated changed-file retrieval with a bounded request budget.
- Rule IDs for traceable findings (`SEC001`, `SEC002`, `OPS001`, `DATA001`, `DEP001`, `TEST001`, `CHG001`).
- Critical security findings force a human-review gate regardless of the configured numeric threshold.
- Explainable 0–100 risk scoring.
- Configurable merge-gate policy.
- Pydantic domain models with a single canonical pull-request snapshot.
- FastAPI + OpenAPI service with health and readiness endpoints.
- Unit, API, and GitHub-adapter tests.
- Docker image running as a non-root user with a container healthcheck.
- GitHub Actions CI for Ruff, Pytest, coverage reporting, and Docker builds.
- CodeQL analysis and Dependabot configuration.

## API contract

### `GET /health`

Returns process health.

### `GET /ready`

Returns service readiness. The baseline implementation deliberately avoids making an external GitHub call on this endpoint.

### `POST /v1/reviews`

Request:

```json
{
  "repository": "octocat/Hello-World",
  "pull_request": 42
}
```

Response shape:

```json
{
  "snapshot": {
    "repository": "octocat/Hello-World",
    "pull_request": 42,
    "title": "Add authentication flow",
    "state": "open",
    "draft": false,
    "filenames": ["src/auth/router.py", "tests/test_auth.py"],
    "additions": 42,
    "deletions": 8,
    "changed_files": 2
  },
  "risk_score": 30,
  "gate": "review_required",
  "findings": [],
  "factors": []
}
```

OpenAPI is available at `/docs`.

## Engineering principles

### Deterministic baseline

The initial decision layer does not depend on an LLM. That makes results reproducible, testable, and suitable as a benchmark baseline for later model-assisted components.

### Evidence before prose

Every finding has a stable rule ID, severity, category, explanation, and affected paths. The intended production system can therefore store or audit decisions without depending on generated narrative.

### Policy is separate from detection

Rules produce risk evidence. The risk engine converts that evidence into a score and policy gate. This separation allows organizations to change thresholds without rewriting the analyzer.

### External APIs behind adapters

GitHub HTTP details are isolated in a small adapter. The analyzer works on an internal snapshot model and does not depend on GitHub response shapes.

### Fail closed on malformed data

Malformed pull-request or changed-file payloads become explicit service errors instead of silent partial reviews.

### Safe runtime defaults

The Docker image uses a dedicated non-root user. Repository and secret files are excluded from the Docker build context.

## Repository layout

```text
forgeai/
├── src/forgeai/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   └── services/
│       ├── github_client.py
│       ├── analyzer.py
│       └── risk.py
├── tests/
│   ├── test_analyzer.py
│   ├── test_api.py
│   └── test_github_client.py
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── codeql.yml
│   └── dependabot.yml
├── docs/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── pyproject.toml
├── SECURITY.md
└── LICENSE
```

## Roadmap to the full platform

### Phase 1 — review intelligence

1. LLM-assisted review planning with structured JSON outputs.
2. Provider abstraction for OpenAI-compatible and hosted model backends.
3. Repository-aware retrieval over changed code, tests, ownership, and configuration.
4. CodeQL and dependency-review result ingestion.
5. Offline benchmark suite with seeded repositories and regression thresholds.

### Phase 2 — controlled engineering actions

6. GitHub Actions execution adapter for checks and artifact collection.
7. MCP-based tool gateway with strict allowlists and action permissions.
8. Human approval state machine before write operations.
9. Idempotency keys, audit events, and durable review records.

### Phase 3 — production operations

10. Postgres persistence and review history.
11. Redis-backed asynchronous job execution.
12. OpenTelemetry traces, Prometheus metrics, and structured logs.
13. Cost, latency, rule-hit, and model-quality telemetry.
14. Authentication, organization-level policies, and rate limiting.

## Local development

Requirements: Python 3.11+, Docker, and a GitHub token when reviewing private repositories.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Run the quality gates locally:

```bash
ruff check src tests
pytest --cov=forgeai --cov-report=term-missing
```

Run the service in Docker:

```bash
docker compose up --build
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `GITHUB_TOKEN` | GitHub API token | empty |
| `RISK_GATE_THRESHOLD` | Maximum numeric score allowed by the baseline policy | `60` |
| `HTTP_TIMEOUT_SECONDS` | GitHub request timeout | `15` |

The public GitHub API can be used without a token for public repositories, subject to GitHub's API limits. Supply `GITHUB_TOKEN` for authenticated access.

## Status

ForgeAI `0.2.0` is the hardened deterministic core. The AI-agent, retrieval, persistence, and controlled-action layers are intentionally staged as separate capabilities so each can be evaluated before being connected to production automation.

## License

MIT
