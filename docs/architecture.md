# ForgeAI Architecture

## System boundary

ForgeAI currently has three trust boundaries:

1. **GitHub boundary** — external repository and pull-request data is fetched through `GitHubClient` and validated into the internal `PullRequestSnapshot` model.
2. **Decision boundary** — the analyzer produces deterministic findings and the risk engine applies policy. No model output is required to make the baseline decision.
3. **API boundary** — FastAPI exposes typed review requests and reports to CI/CD systems or future platform components.

```text
                   +----------------------+
                   |   GitHub REST API    |
                   +----------+-----------+
                              |
                         HTTPS / token
                              |
                   +----------v-----------+
                   |    GitHubClient      |
                   | validation + retry   |
                   | bounded pagination   |
                   +----------+-----------+
                              |
                    PullRequestSnapshot
                              |
                   +----------v-----------+
                   |   Deterministic      |
                   |    Rule Analyzer     |
                   +----------+-----------+
                              |
                  Findings + Risk Factors
                              |
                   +----------v-----------+
                   |      Risk Engine     |
                   | score + policy gate  |
                   +----------+-----------+
                              |
                       ReviewReport
                              |
                   +----------v-----------+
                   |      FastAPI API     |
                   +----------------------+
```

## Why deterministic analysis is the baseline

The first layer is intentionally deterministic. Rules have stable IDs, affected paths, severities, and rationales. This gives ForgeAI a reproducible reference implementation before LLM-assisted reasoning is introduced.

A future model layer should enrich the report rather than silently replace the policy engine. Model-generated conclusions should be structured, validated, measured against the deterministic baseline, and visible in the audit trail.

## Planned production architecture

The production target adds the following components:

```text
GitHub App / Webhook
        |
        v
 API Gateway ---- authentication / rate limits
        |
        v
 Review Orchestrator ---- Postgres review state
        |
        +---- Deterministic Rules
        +---- CodeQL / Dependency Review adapters
        +---- Repository Retrieval
        |          |
        |          +---- object storage / embeddings
        |
        +---- LLM Review Planner
        |          |
        |          +---- provider adapters
        |          +---- evaluation / guardrails
        |
        +---- Policy Engine
        |
        +---- Approval State Machine
        |
        +---- Tool Gateway / MCP
                   |
                   +---- allowlisted read actions
                   +---- approval-gated write actions

Observability: OpenTelemetry + metrics + audit events
Async work: Redis queue / workers
```

## Security model

Write operations should be disabled by default. Any future tool execution layer should enforce:

- explicit action allowlists;
- repository and branch scope checks;
- authenticated user or workload identity;
- human approval for mutating actions;
- idempotency for retries;
- immutable audit events;
- bounded command execution time and output size;
- secret redaction before logs or model prompts.

## Non-goals for the baseline

The current service is not a full autonomous coding agent. It does not push code, merge pull requests, execute arbitrary shell commands, or make unbounded external tool calls. Those capabilities belong to later phases with their own security and evaluation controls.
