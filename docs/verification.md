# Verification & Evidence

ForgeAI's baseline risk decision is deterministic and its benchmark/security corpus is versioned in the repository.

| Evidence | Source | Reproduction |
|---|---|---|
| Rule-engine evaluation | evals/cases.jsonl | python scripts/run_eval.py --output artifacts/benchmark.json |
| Security evaluation | evals/security_cases.json | python scripts/run_security_eval.py --output artifacts/security.json |
| Database migrations | migrations/ | alembic upgrade head |
| Test suite | tests/ | pytest --cov=forgeai |
| Static analysis | .github/workflows/codeql.yml | CodeQL |
| Workflow security | .github/workflows/scorecard.yml | OpenSSF Scorecard |

## Result integrity

CI records the repository commit and UTC generation time in the JSON evidence artifacts. Benchmark numbers must not be copied into documentation without the dataset, denominator, configuration, and reproduction command.