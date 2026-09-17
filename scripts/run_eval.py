from __future__ import annotations

import json
from pathlib import Path

from forgeai.models import PullRequestSnapshot
from forgeai.services.evaluator import EvaluationCase, evaluate


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            EvaluationCase(
                name=str(payload["name"]),
                snapshot=PullRequestSnapshot.model_validate(payload["snapshot"]),
                expected_rule_ids=frozenset(payload["expected_rule_ids"]),
            )
        )
    return cases


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    metrics = evaluate(load_cases(root / "evals" / "cases.jsonl"))
    print(f"cases={metrics.cases}")
    print(f"exact_match_cases={metrics.exact_match_cases}")
    print(f"precision={metrics.precision:.3f}")
    print(f"recall={metrics.recall:.3f}")


if __name__ == "__main__":
    main()
