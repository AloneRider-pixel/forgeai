# ForgeAI — AI Software Engineering Platform

ForgeAI is a production-oriented engineering review service that analyzes GitHub pull requests for change risk, security-sensitive changes, dependency impact, infrastructure changes, and test impact.

The project starts with a deterministic analysis core so every finding is explainable and testable. LLM-assisted review, repository context, tool execution, evaluation, and observability are planned as later layers rather than being hard-coded into the domain logic.

## Architecture

```text
GitHub Pull Request
        |
        v
   FastAPI API
        |
        v
   GitHub Adapter
        |
        v
 Change Analyzer
        |
        +---- security surface
        +---- infrastructure changes
        +---- data / migration changes
        +---- dependency changes
        +---- test-impact heuristics
        |
        v
    Risk Engine
        |
        +---- weighted score
        +---- policy gate
        +---- severity findings
        |
        v
 Typed Review Report
```

## Why this project exists

Most code-review assistants are presented as chat interfaces. ForgeAI treats software engineering review as a system problem: ingest structured repository changes, apply deterministic policy, produce auditable findings, and leave clear extension points for model-assisted reasoning.

## Current capabilities

- GitHub pull-request metadata and changed-file retrieval.
- Risk classification for authentication, authorization, IAM, OAuth, secrets, infrastructure, migrations, dependencies, and source changes without visible tests.
- Explainable 0–100 risk scoring.
- Configurable merge-gate policy.
- Typed Pydantic response models.
- FastAPI + OpenAPI API.
- Unit and API tests.
- Docker and Docker Compose support.
- GitHub Actions CI with Ruff, Pytest, and container build validation.
- CodeQL workflow for the Python service.

## API

### `GET /health`

Returns service health.

### `POST /v1/reviews`

Example request:

```json
{
  "repository": "octocat/Hello-World",
  "pull_request": 42
}
```

The response includes the pull-request metadata, risk score, gate decision, findings, and risk factors.

### `GET /docs`

Interactive OpenAPI documentation.

## Local development

Requirements: Python 3.11+, Docker, and a GitHub token when reviewing private repositories.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Open `http://localhost:8000/docs`.

Run tests:

```bash
pytest
```

Run lint:

```bash
ruff check src tests
```

Run with Docker:

```bash
docker compose up --build
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `GITHUB_TOKEN` | GitHub API token | empty |
| `RISK_GATE_THRESHOLD` | Maximum score allowed by the baseline policy | `60` |
| `HTTP_TIMEOUT_SECONDS` | GitHub API timeout | `15` |

The public GitHub API can be used without a token for public repositories, subject to GitHub's API limits. Supply `GITHUB_TOKEN` for authenticated access.

## Engineering decisions

### Deterministic core first

The baseline analyzer does not require an LLM. That makes behavior reproducible and allows future AI components to be evaluated against a stable baseline.

### Policy as a primitive

A risk score is accompanied by explicit factors and a gate decision. Consumers can inspect why a review crossed the policy threshold.

### GitHub behind an adapter

External API payloads are translated into a small internal snapshot model. The analysis engine does not depend directly on GitHub HTTP details.

### Fail closed on malformed upstream data

Unexpected pull-request data is rejected rather than silently producing a partial review.

## Project structure

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
│   └── test_api.py
├── .github/workflows/
│   ├── ci.yml
│   └── codeql.yml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── SECURITY.md
```

## Roadmap

1. LLM-assisted review planning with structured outputs.
2. GitHub Actions execution and artifact collection.
3. CodeQL and dependency-review result ingestion.
4. MCP-based, allowlisted tool gateway.
5. Repository semantic search and retrieval.
6. Offline evaluation benchmark over seeded repositories.
7. OpenTelemetry traces, Prometheus metrics, and cost/latency telemetry.
8. Human approval workflow before automated actions.

## License

MIT
