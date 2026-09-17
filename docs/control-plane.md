# ForgeAI Control Plane

The control plane turns a synchronous PR reviewer into a persisted, asynchronous workflow.

## Review lifecycle

```text
POST /v1/jobs
      |
      v
    queued
      |
      v
    running
      |
      +----> failed
      |
      v
  succeeded
      |
      v
  evidence ingestion
      |
      v
review_required / eligible
      |
      v
human approval
      |
      v
allowlisted tool execution
```

## Persistence

The async SQLAlchemy layer stores:

- review job request and lifecycle state;
- deterministic review report and planner output;
- external analysis evidence;
- approval decisions and rationale;
- tool execution records.

SQLite is the local default. PostgreSQL is used by the Docker Compose production topology.

## Queueing

`RedisJobQueue` uses a Redis list and blocking pop. The API enqueues a job and returns `202 Accepted`; a separate worker consumes the job and persists its terminal state. The application uses an in-process queue when `REDIS_URL` is empty, which keeps local development self-contained.

## Evidence

The SARIF ingestion endpoint accepts CodeQL and dependency-review shaped results. Evidence is normalized into a common model and can raise the effective review gate when high or critical findings are present.

## Approval and execution

Side-effecting automation is deliberately separated from analysis. A job must be `succeeded` and explicitly `approved` before the execution endpoint can invoke the tool gateway. Workflow IDs are allowlisted using `ALLOWED_GITHUB_WORKFLOWS`.

The gateway currently exposes one side-effecting capability:

```text
github.workflow_dispatch
```

The `/mcp` endpoint provides a small JSON-RPC-compatible surface for `tools/list` and `tools/call`, with the same approval checks.

## Observability

Review processing emits an OpenTelemetry span and Prometheus metrics. Scrape `GET /metrics` from the API service.
