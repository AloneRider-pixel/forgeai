# ForgeAI v0.6 architecture

The control plane now separates four concerns:

```text
GitHub webhook
     |
 signed + idempotent
     v
Webhook inbox -> durable queue -> review worker
                           |
                           +--> deterministic risk engine
                           +--> bounded LLM planner
                           +--> semantic retrieval index
                           +--> evidence / approval state
                           +--> governed tool gateway

PostgreSQL <--- Alembic schema migrations
Redis --------> asynchronous job transport
OTLP ----------> correlated review traces
RBAC ----------> reader / reviewer / operator boundaries
```

The retrieval index is repository/ref scoped and stores source SHA, bounded content, and optional embedding vectors. External LLM/embedding providers remain optional; deterministic local fallbacks preserve testability.
