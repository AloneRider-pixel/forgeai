# ForgeAI

[![CI](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/forgeai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Production-oriented GitHub pull-request risk and review platform.**

ForgeAI combines a deterministic risk engine with bounded repository context and an optional LLM review planner. The core decision path remains usable without an external model, while model-assisted reasoning is constrained by typed inputs, context limits, secret redaction, and explicit fallback behavior.

> **Portfolio focus:** backend architecture + developer tooling + secure LLM integration + GitHub automation.

## Why ForgeAI

LLM-assisted code review can introduce a second class of risk: the review model itself must be prevented from turning untrusted repository content into instructions. ForgeAI treats repository files as data, keeps the deterministic baseline independent of the LLM, and makes the model an optional planning layer rather than a trusted decision-maker.

```text
GitHub Pull Request
        ↓
Deterministic risk analysis
  ├── path classification
  ├── security rules
  ├── test impact
  ├── change size
  └── risk score / merge gate
        ↓
Optional assisted review
  ├── bounded context retrieval
  ├── secret redaction
  └── LLM review planner
        ↓
Structured review plan
```

## Core capabilities

### Deterministic risk engine

- Security-sensitive path detection.
- Credential and private-key detection.
- Infrastructure/deployment change detection.
- Database and migration change detection.
- Dependency-manifest change detection.
- Test-impact heuristics.
- Large-change surface detection.
- Explainable 0–100 risk score.
- Fail-closed gate for critical findings.
- Stable rule IDs such as `SEC001`, `OPS001`, and `TEST001`.

### GitHub integration

- Pull-request metadata retrieval.
- Changed-file pagination with bounded page counts.
- Retry handling for rate limits and transient failures.
- Head SHA and branch metadata.
- Targeted file-content retrieval.
- Validation of malformed upstream payloads.

### Assisted review pipeline

`POST /v1/reviews/assisted` starts from the deterministic baseline and adds a bounded set of relevant source files.

Context controls include:

- configurable file and character limits;
- lexical relevance ranking;
- secret/private-key redaction;
- no execution of repository content;
- an explicit prompt-injection boundary in the planner system instruction.

### LLM planner

ForgeAI accepts an OpenAI-compatible `/chat/completions` endpoint through configuration. Structured output is validated, and the system falls back to the deterministic planner when the model is unavailable, times out, returns malformed output, or violates the expected schema.

No model API key is required for the deterministic path, local development, or CI.

## Evaluation harness

The deterministic analyzer is evaluated against versioned fixture cases in `evals/cases.jsonl` when that fixture set is present.

```bash
python scripts/run_eval.py
```

The evaluation script reports case count, exact-match cases, precision, and recall. Keep benchmark results tied to a versioned fixture set and document the evaluation methodology before publishing performance claims.

## API

### `GET /health`
Liveness endpoint.

### `GET /ready`
Readiness endpoint.

### `POST /v1/reviews`
Runs the deterministic baseline reviewer.

```json
{
  "repository": "octocat/Hello-World",
  "pull_request": 42
}
```

### `POST /v1/reviews/assisted`
Runs deterministic analysis, bounded repository-context retrieval, and review planning.

```json
{
  "repository": "octocat/Hello-World",
  "pull_request": 42,
  "use_llm": false,
  "max_context_files": 5,
  "max_file_chars": 12000
}
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

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI |
| GitHub | GitHub API integration |
| Review engine | Deterministic rules + typed models |
| LLM | OpenAI-compatible provider |
| Quality | Pytest, Ruff |
| Security | Secret redaction, prompt-injection boundary, CodeQL |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Repository structure

```text
forgeai/
├── src/forgeai/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   └── services/
│       ├── analyzer.py
│       ├── context.py
│       ├── evaluator.py
│       ├── github_client.py
│       ├── planner.py
│       └── risk.py
├── tests/
├── evals/cases.jsonl
├── scripts/run_eval.py
├── .github/workflows/ci.yml
├── .github/workflows/codeql.yml
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Local development

Requirements: Python 3.11+ and Docker. A GitHub token is required for authenticated GitHub API access.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Open `http://localhost:8000/docs`.

### Quality checks

```bash
pytest
ruff check src tests scripts
python scripts/run_eval.py
```

### Docker

```bash
docker compose up --build
```

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `GITHUB_TOKEN` | GitHub API token | empty |
| `RISK_GATE_THRESHOLD` | Baseline risk threshold | `60` |
| `HTTP_TIMEOUT_SECONDS` | GitHub API timeout | `15` |
| `CONTEXT_MAX_FILES` | Max files in assisted context | `5` |
| `CONTEXT_MAX_CHARS` | Max characters per context file | `12000` |
| `LLM_BASE_URL` | OpenAI-compatible API base URL | empty |
| `LLM_API_KEY` | LLM API key | empty |
| `LLM_MODEL` | Model name | `gpt-4.1-mini` |
| `LLM_TIMEOUT_SECONDS` | LLM timeout | `30` |

## Roadmap

- CodeQL and dependency-review ingestion.
- Repository-wide semantic retrieval with embeddings.
- Persistent review history and Redis-backed asynchronous jobs.
- GitHub Actions execution with explicit approval gates.
- MCP tool gateway with allowlisted capabilities.
- OpenTelemetry traces, metrics, latency, and model-cost telemetry.
- Regression benchmarks with seeded repositories and adversarial prompt-injection fixtures.

## License

MIT
