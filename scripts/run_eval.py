from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from forgeai.models import PullRequestSnapshot
from forgeai.services.evaluator import EvaluationCase, evaluate


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            EvaluationCase(
                name=str(payload['name']),
                snapshot=PullRequestSnapshot.model_validate(payload['snapshot']),
                expected_rule_ids=frozenset(payload['expected_rule_ids']),
            )
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description='Run deterministic ForgeAI evaluation cases.')
    parser.add_argument('--output', type=Path, help='Optional JSON evidence output path.')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    dataset_path = root / 'evals' / 'cases.jsonl'
    cases = load_cases(dataset_path)
    metrics = evaluate(cases)

    payload = {
        'evaluation': 'deterministic-rule-engine',
        'dataset': str(dataset_path.relative_to(root)),
        'cases': metrics.cases,
        'exact_match_cases': metrics.exact_match_cases,
        'exact_match_rate': (round(metrics.exact_match_cases / metrics.cases, 6) if metrics.cases else 0.0),
        'precision': round(metrics.precision, 6),
        'recall': round(metrics.recall, 6),
        'commit': os.getenv('GITHUB_SHA'),
        'generated_at_utc': datetime.now(UTC).isoformat(),
    }

    print(f"cases={payload['cases']}")
    print(f"exact_match_cases={payload['exact_match_cases']}")
    print(f"precision={payload['precision']:.3f}")
    print(f"recall={payload['recall']:.3f}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()