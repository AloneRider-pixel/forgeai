# ForgeAI Control Plane

The control plane turns a synchronous PR reviewer into a persisted, asynchronous workflow and adds an event-driven ingestion path for GitHub pull-request activity.

## Review lifecycle

```text
GitHub webhook
      |
      v
signature verification
      |
      v
idempotent delivery inbox
      |
      v
pending outbox delivery
      |
      v
job queue
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
- tool execution records;
- GitHub webhook delivery payloads, dispatch attempts, job linkage, and terminal delivery state.

SQLite is the local default. PostgreSQL is used by the Docker Compose production topology.

## Event-driven ingestion

`POST /v1/webhooks/github` accepts GitHub webhook deliveries after validating the HMAC SHA-256 signature from `X-Hub-Signature-256`. The endpoint caps payload size, normalizes pull-request events, and ignores unsupported event types/actions.

Supported pull-request actions are:

```text
opened
reopened
synchronize
ready_for_review
```

Each `X-GitHub-Delivery` value is an idempotency key. A duplicate delivery returns the original job ID instead of creating another review job.

## Durable delivery workflow

Webhook ingestion and job creation are committed together. A delivery first enters `pending`, and a background dispatcher moves it onto the configured queue. This is an outbox-style handoff: a process restart leaves pending deliveries in the database for later dispatch.

Dispatch failures increment `attempts`. After `WEBHOOK_DISPATCH_MAX_ATTEMPTS`, the delivery becomes `dead_lettered` and the linked job is marked failed. Review execution failures mark the delivery `failed` and preserve the error for operator inspection.

Use `GET /v1/webhooks/github/{delivery_id}` to inspect delivery state without exposing the stored payload.

## Queueing

`RedisJobQueue` uses a Redis list and blocking pop. The API enqueues a job and returns `202 Accepted`; a separate worker consumes the job and persists its terminal state. The application uses an in-process queue when `REDIS_URL` is empty, which keeps local development self-contained.

The worker treats duplicate queue messages idempotently because only `queued` jobs are eligible for processing; a job that is already `running`, `succeeded`, or `failed` is skipped.

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
