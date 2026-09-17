# ForgeAI

ForgeAI is a production-oriented GitHub pull-request review platform. It combines a deterministic risk engine with bounded repository context and an optional LLM review planner.

The architecture is intentionally layered: the core review decision does not depend on an LLM, while model-assisted reasoning is constrained by typed inputs, bounded context, secret redaction, and explicit fallback behavior.

## Architecture

```text
                         GitHub Pull Request
                                  |
                                  v
                         +------------------+
                         |   FastAPI API    |
                         +--------+---------+
                                  |
                     +------------+------------+
                     |                         |
                     v                         v
              Deterministic Core        Assisted Pipeline
              ------------------        -----------------
              path classification      PR + changed files
              security rules            repository content
              test impact               secret redaction
              change size               bounded retrieval
              risk scoring                      |
              merge gate                       v
                     |                  Review Planner
                     |                  /           \
                     |           deterministic     LLM
                     |                 \             /
                     +------------------+----------+
                                        |
                                        v
                              Structured Review Plan
```

## Current capabilities

### Deterministic risk analysis

- Security-sensitive path detection.
- Credential and private-key file detection.
- Infrastructure and deployment change detection.
- Database and migration change detection.
- Dependency-manifest change detection.
- Test-impact heuristics.
- Large-change surface detection.
- Explainable 0-100 risk score.
- Fail-closed gate for critical findings.
- Stable rule IDs such as `SEC001`, `SEC002`, `OPS001`, and `TEST001`.

### GitHub integration

- Pull-request metadata retrieval.
- Changed-file pagination with bounded page count.
- Retry handling for rate limits and transient upstream failures.
- Pull-request head SHA and branch metadata.
- File-content retrieval for targeted repository context.
- Explicit validation for malformed upstream payloads.

### Assisted review pipeline

`POST /v1/reviews/assisted` builds a review bundle from the same deterministic baseline and then retrieves a bounded set of relevant source files.

Context handling includes:

- configurable file and character limits;
- lexical relevance ranking over changed files;
- secret-value and private-key redaction;
- no execution of repository content;
- explicit prompt-injection boundary in the LLM system instruction.

### LLM planner

ForgeAI supports an OpenAI-compatible `/chat/completions` endpoint through configuration. The planner expects structured JSON and falls back to the deterministic planner on missing configuration, transport failure, malformed output, or invalid fields.

No model API key is required to run ForgeAI locally or in CI.

### Evaluation harness

The deterministic analyzer is evaluated against versioned fixture cases in `evals/cases.jsonl`.

Run:

```bash
python scripts/run_eval.py
```

The harness reports case count, exact-match cases, precision, and recall.

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

The risk engine only consumes a typed pull-request snapshot. GitHub HTTP behavior is isolated behind an adapter, and planning is isolated behind a planner interface.

### Untrusted repository content

Repository files are treated as data, not instructions. Context is bounded before it reaches a planner, common secret values are redacted, and LLM-assisted planning is optional.

### Deterministic fallback

An external model is an enhancement rather than a dependency for the review decision. A planner failure never removes the deterministic baseline report.

### Bounded upstream access

Changed-file retrieval is paginated with a maximum page count. Context retrieval is limited by both file count and characters per file.

## Local development

Requirements: Python 3.11+, Docker, and a GitHub token for authenticated or private-repository access.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Open `http://localhost:8000/docs`.

Run tests and lint:

```bash
pytest
ruff check src tests scripts
python scripts/run_eval.py
```

Run with Docker:

```bash
docker compose up --build
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `GITHUB_TOKEN` | GitHub API token | empty |
| `RISK_GATE_THRESHOLD` | Maximum baseline risk score before review | `60` |
| `HTTP_TIMEOUT_SECONDS` | GitHub API timeout | `15` |
| `CONTEXT_MAX_FILES` | Maximum files added to assisted context | `5` |
| `CONTEXT_MAX_CHARS` | Maximum characters per context file | `12000` |
| `LLM_BASE_URL` | OpenAI-compatible API base URL | empty |
| `LLM_API_KEY` | LLM API key | empty |
| `LLM_MODEL` | Model name passed to the provider | `gpt-4.1-mini` |
| `LLM_TIMEOUT_SECONDS` | LLM request timeout | `30` |

## Project structure

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
│   ├── test_analyzer.py
│   ├── test_api.py
│   ├── test_api_assisted.py
│   ├── test_context.py
│   ├── test_evaluator.py
│   ├── test_github_client.py
│   └── test_planner.py
├── evals/cases.jsonl
├── scripts/run_eval.py
├── .github/workflows/ci.yml
├── .github/workflows/codeql.yml
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Roadmap

1. CodeQL and dependency-review ingestion.
2. Repository-wide semantic retrieval with embeddings.
3. Persistent review history and Redis-backed asynchronous jobs.
4. GitHub Actions execution with explicit approval gates.
5. MCP tool gateway with allowlisted capabilities.
6. OpenTelemetry traces, metrics, latency, and model-cost telemetry.
7. Regression benchmarks across seeded repositories and adversarial prompt-injection fixtures.

## License

MIT
