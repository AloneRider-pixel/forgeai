# Evidence and reproducibility policy

ForgeAI intentionally separates deterministic risk decisions from optional model-assisted planning.

## Evidence classes

- **Capability:** implemented behavior verified by source code and tests.
- **Design target:** intended threshold or SLO.
- **Measured result:** benchmark output tied to a named dataset/workload, configuration, sample count, environment, and commit.
- **Synthetic/adversarial test result:** controlled test corpus used to validate system behavior.

## Risk and security claims

Published detection or risk-quality claims should reference the exact version of evals/cases.jsonl, the adversarial corpus version, scoring rules, run command, and generated output.

## LLM claims

Do not attribute deterministic rule-engine performance to the LLM. Model-assisted results should record provider/model/version, prompt or planner configuration, dataset version, and evaluation method.

## CI boundary

A green CI run establishes that the configured tests, evaluation harnesses, migrations, lint, and Docker build passed. It is not a guarantee of production security or review quality.
